"""Load HLTV map results and group them into matches (series).

Source: HLTV's map results list (hltv.org/stats/matches) with the filters
"LAN" and "ranking: top 50", 2024-12-01 to 2026-11-17, collected once in the
user's own browser (see docs/JOURNAL.md, Step 6a). The ranking filter uses
the ranking at the time of each match, not today's: 117 different teams
appear, some only in early months. The raw file stays local in
data/raw/hltv/ and is not committed: it is HLTV's data.

Each row is one map: map ID, date, both teams (HLTV ID, name, rounds won),
map name, event (HLTV ID, name). The list has no match ID, so maps are
grouped into series here: same event, same two teams, consecutive maps
no more than a day apart. A series of 1 map is a BO1; 2-3 maps a BO3
(4-5 maps a BO5).
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class MapResult:
    map_id: int
    date: date
    team1_id: str
    team1: str
    team1_rounds: int
    team2_id: str
    team2: str
    team2_rounds: int
    map: str
    event_id: str
    event: str

    @property
    def winner(self) -> str:
        return self.team1 if self.team1_rounds > self.team2_rounds else self.team2

    @property
    def winner_id(self) -> str:
        return self.team1_id if self.team1_rounds > self.team2_rounds else self.team2_id

    @property
    def loser_id(self) -> str:
        return self.team2_id if self.team1_rounds > self.team2_rounds else self.team1_id


@dataclass(frozen=True)
class Series:
    date: date                  # date of the first map
    event_id: str
    event: str
    team_a: str                 # series winner (by maps won)
    team_b: str
    team_a_id: str
    team_b_id: str
    maps_a: int
    maps_b: int
    best_of: int                # 1, 3 or 5
    maps: tuple[MapResult, ...]


def load_maps(path: Path) -> list[MapResult]:
    out = []
    with open(path, newline="", encoding="utf-8") as fp:
        for r in csv.DictReader(fp):
            if not r["team1_rounds"] or not r["team2_rounds"] or r["team1_rounds"] == r["team2_rounds"]:
                continue  # unfinished or drawn map
            out.append(MapResult(
                map_id=int(r["mapstatsid"]),
                date=datetime.strptime(r["date"], "%d/%m/%y").date(),
                team1_id=r["team1_id"], team1=r["team1"], team1_rounds=int(r["team1_rounds"]),
                team2_id=r["team2_id"], team2=r["team2"], team2_rounds=int(r["team2_rounds"]),
                map=r["map"], event_id=r["event_id"], event=r["event"],
            ))
    # Same map listed twice (pagination shifts while collecting): keep one.
    unique = {m.map_id: m for m in out}
    return sorted(unique.values(), key=lambda m: m.map_id)


def _make_series(maps: list[MapResult]) -> Series:
    wins: dict[str, int] = {}
    names: dict[str, str] = {}
    for m in maps:
        wins[m.winner_id] = wins.get(m.winner_id, 0) + 1
        names[m.team1_id], names[m.team2_id] = m.team1, m.team2
    ids = list(names)
    a, b = sorted(ids, key=lambda t: -wins.get(t, 0))
    n = len(maps)
    best_of = 1 if n == 1 else 3 if n <= 3 else 5
    return Series(maps[0].date, maps[0].event_id, maps[0].event, names[a], names[b], a, b,
                  wins.get(a, 0), wins.get(b, 0), best_of, tuple(maps))


def group_series(maps: list[MapResult]) -> list[Series]:
    """Group maps into series (see module docstring for the rule).

    Within one event and pair of teams, maps no more than a day apart form
    a cluster. A cluster of up to 3 maps is one series. A longer cluster is
    split: a series closes when a team reaches 2 map wins (BO3), unless the
    cluster has no more than 5 maps and someone reaches 3 (BO5). A series
    with no winner (e.g. 1-1: a BO2, or a map missing from the list) is
    dropped.
    """
    clusters: dict[tuple, list[list[MapResult]]] = {}
    for m in maps:  # maps are in map-ID order, i.e. roughly chronological
        key = (m.event_id, frozenset((m.team1_id, m.team2_id)))
        runs = clusters.setdefault(key, [])
        if runs and (m.date - runs[-1][-1].date).days <= 1:
            runs[-1].append(m)
        else:
            runs.append([m])
    out = []
    for runs in clusters.values():
        for run in runs:
            if len(run) <= 3:
                out.append(_make_series(run))
                continue
            wins = {}
            for m in run:
                wins[m.winner_id] = wins.get(m.winner_id, 0) + 1
            if len(run) <= 5 and max(wins.values()) == 3:
                out.append(_make_series(run))
                continue
            current: list[MapResult] = []
            tally: dict[str, int] = {}
            for m in run:
                current.append(m)
                tally[m.winner_id] = tally.get(m.winner_id, 0) + 1
                if max(tally.values()) == 2:
                    out.append(_make_series(current))
                    current, tally = [], {}
            if current:
                out.append(_make_series(current))
    out = [s for s in out if s.maps_a != s.maps_b]
    return sorted(out, key=lambda s: (s.date, s.maps[0].map_id))


# --- linking HLTV series to Valve's match list ----------------------------------

def norm_name(name: str) -> str:
    """Lowercase letters and digits only, without a leading 'team'."""
    s = re.sub(r"[^a-z0-9]", "", name.lower())
    return s[4:] if s.startswith("team") and len(s) > 6 else s


def link_series(series: list[Series], matches: list, max_days: int = 1) -> dict[int, Series]:
    """Find each HLTV series in Valve's match list: {match index: series}.

    `matches` needs .date, .winner and .loser. A link needs a Valve match
    within `max_days` of the series' first map, with the same winner and
    loser. Names are compared after norm_name. Teams whose HLTV name differs
    from Valve's (e.g. a short form) are learned first: when one side of a
    meeting matches by name, the other side's HLTV team ID votes for the
    Valve name it faced; a name is accepted with 2+ votes and 80%+ of that
    ID's votes.
    """
    by_date: dict[date, list[int]] = defaultdict(list)
    for i, m in enumerate(matches):
        by_date[m.date].append(i)
    offsets = sorted(range(-max_days, max_days + 1), key=abs)

    def candidates(s: Series):
        for dd in offsets:
            yield from by_date.get(s.date + timedelta(days=dd), [])

    votes: dict[str, Counter] = defaultdict(Counter)
    for s in series:
        for i in candidates(s):
            m = matches[i]
            sides = ((s.team_a_id, s.team_a, m.winner), (s.team_b_id, s.team_b, m.loser))
            for (hid, hname, vname), (_, oname, ovname) in (sides, sides[::-1]):
                if norm_name(oname) == norm_name(ovname) and norm_name(hname) != norm_name(vname):
                    votes[hid][vname] += 1
    alias = {}
    for hid, c in votes.items():
        name, n = c.most_common(1)[0]
        if n >= 2 and n >= 0.8 * sum(c.values()):
            alias[hid] = name

    def same(hid: str, hname: str, vname: str) -> bool:
        return norm_name(hname) == norm_name(vname) or alias.get(hid) == vname

    links: dict[int, Series] = {}
    for s in series:
        for i in candidates(s):
            if i in links:
                continue
            m = matches[i]
            if same(s.team_a_id, s.team_a, m.winner) and same(s.team_b_id, s.team_b, m.loser):
                links[i] = s
                break
    return links
