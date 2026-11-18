"""Parse Valve Regional Standings (VRS) snapshots into a match history.

Source: github.com/ValveSoftware/counter-strike_regional_standings, folder
``live/``. Each snapshot is a dated folder ``live/YYYY/details/YYYY_MM_DD/``
holding one markdown page per ranked roster. A page has:
  * a header: team name, current roster, global rank, region, VRS points;
  * a table of every match that roster played in the previous 6 months:
    match ID (unique within the snapshot), date, opponent, W/L, the lineup
    that played, and, only for some wins, an event weight and a LAN flag.

What the tables do NOT contain: map names, scores, BO1/BO3 format, event
names. LAN and event weight are shown only for wins that are among the
roster's ten best for that factor, so they are often unknown.

See docs/decisions/0003-data-sources.md and docs/JOURNAL.md (Step 4).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable

Roster = tuple[str, ...]  # player names, sorted case-insensitively


def _roster(text: str) -> Roster:
    return tuple(sorted((p.strip() for p in text.split(",") if p.strip()), key=str.lower))


def _date(text: str) -> date:
    return date.fromisoformat(text.strip().replace("_", "-"))


@dataclass(frozen=True)
class MatchRow:
    """One line of a roster page's match table, seen from that roster's side."""
    match_id: int
    date: date
    opponent: str
    won: bool
    event_weight: float | None  # None = not shown
    lan: bool | None            # True = LAN, False = online, None = not shown
    roster: Roster              # the lineup that played this match


@dataclass(frozen=True)
class RosterPage:
    snapshot: date
    team: str
    roster: Roster              # lineup at snapshot time
    global_rank: int | None
    region: str | None
    points: float | None        # VRS "Final Rank Value"
    rows: tuple[MatchRow, ...]


@dataclass(frozen=True)
class Match:
    """One match, both sides merged. Rosters are None when the side has no page."""
    date: date
    winner: str
    loser: str
    winner_roster: Roster | None
    loser_roster: Roster | None
    lan: bool | None
    event_weight: float | None
    snapshot: date              # snapshot the record was taken from


_HEADER = {
    "team": re.compile(r"^Team Name:\s*(.*?)<br />"),
    "roster": re.compile(r"^Roster:\s*(.*?)<br />"),
    "global_rank": re.compile(r"^Global Rank:\s*\[(\d+)\]"),
    "region": re.compile(r"^Region:\s*\[([^\]]+)\]"),
    "points": re.compile(r"^Final Rank Value:\s*([-\d.]+)"),
}


def parse_page(path: Path, snapshot: date) -> RosterPage:
    head: dict[str, str] = {}
    rows: list[MatchRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|"):
            c = [x.strip() for x in line.split("|")]
            # Match table rows: | played | id | date | opponent | W/L | age | event | bounty | network | LAN | H2H | roster |
            if len(c) >= 14 and c[1].isdigit() and c[2].isdigit() and c[5] in ("W", "L"):
                lan_cell = c[10]
                rows.append(MatchRow(
                    match_id=int(c[2]),
                    date=_date(c[3]),
                    opponent=c[4],
                    won=c[5] == "W",
                    event_weight=None if c[7] == "-" else float(c[7]),
                    lan=None if lan_cell == "-" else lan_cell.startswith("1"),
                    roster=_roster(c[12]),
                ))
            continue
        for key, rx in _HEADER.items():
            if key not in head:
                m = rx.match(line)
                if m:
                    head[key] = m.group(1).strip()
    if "team" not in head:
        raise ValueError(f"no team name in {path}")
    return RosterPage(
        snapshot=snapshot,
        team=head["team"],
        roster=_roster(head.get("roster", "")),
        global_rank=int(head["global_rank"]) if "global_rank" in head else None,
        region=head.get("region"),
        points=float(head["points"]) if "points" in head else None,
        rows=tuple(rows),
    )


def snapshot_dirs(vrs_root: Path) -> list[tuple[date, Path]]:
    """All live/YYYY/details/YYYY_MM_DD folders, oldest first."""
    out = [(_date(d.name), d) for d in (vrs_root / "live").glob("*/details/*") if d.is_dir()]
    return sorted(out)


def load_snapshot(folder: Path, snapshot: date) -> list[RosterPage]:
    return [parse_page(p, snapshot) for p in sorted(folder.glob("*.md"))]


def matches_in_snapshot(pages: Iterable[RosterPage]) -> list[Match]:
    """Merge the two sides of each match (same match ID within one snapshot)."""
    by_id: dict[int, list[tuple[RosterPage, MatchRow]]] = defaultdict(list)
    for page in pages:
        for row in page.rows:
            by_id[row.match_id].append((page, row))
    out = []
    for mid, sides in by_id.items():
        win_side = next(((p, r) for p, r in sides if r.won), None)
        loss_side = next(((p, r) for p, r in sides if not r.won), None)
        ref_page, ref_row = win_side or loss_side
        if win_side:
            winner, loser = win_side[0].team, win_side[1].opponent
        else:
            winner, loser = loss_side[1].opponent, loss_side[0].team
        if win_side and loss_side and loss_side[0].team != loser:
            loser = loss_side[0].team  # trust the page's own name over the opponent label
        out.append(Match(
            date=ref_row.date,
            winner=winner,
            loser=loser,
            winner_roster=win_side[1].roster if win_side else None,
            loser_roster=loss_side[1].roster if loss_side else None,
            lan=win_side[1].lan if win_side else None,
            event_weight=win_side[1].event_weight if win_side else None,
            snapshot=ref_page.snapshot,
        ))
    return out


LAG_DAYS = 14  # a match entered late can first appear in the following snapshot


def _keys(m: Match) -> list[tuple]:
    """Ways to recognise the same match in another snapshot: names, and lineups."""
    keys = [("name", m.date, m.winner, m.loser)]
    if m.winner_roster and m.loser_roster:
        keys.append(("lineup", m.date, m.winner_roster, m.loser_roster))
    return keys


def build_history(snapshots: Iterable[tuple[date, list[Match]]], lag_days: int = LAG_DAYS) -> list[Match]:
    """Combine overlapping 6-month snapshots into one deduplicated history.

    The problem: snapshots overlap (each covers the previous 6 months) and
    match IDs are only unique within a snapshot. Matching records across
    snapshots by team names fails, because Valve relabels old matches when a
    team is renamed (e.g. "PERA" later appears as "ex-PERA"). A first version
    that matched by names counted about 6,500 matches twice.

    The approach: take each match from the first snapshot after it was
    played, i.e. snapshot k contributes the matches dated after snapshot k-1.
    A match entered late (dated up to ``lag_days`` before snapshot k-1 but
    missing from it) is also taken from snapshot k. Team names are therefore
    the ones in use shortly after the match.

    LAN flags and event weights are shown only for a roster's "ten best"
    wins, and that list changes over time, so a flag missing in the chosen
    snapshot is filled in from any snapshot that shows it (recognised by
    names or by both lineups).
    """
    snaps = sorted(snapshots, key=lambda x: x[0])
    lan_seen: dict[tuple, bool] = {}
    ev_seen: dict[tuple, float] = {}
    for _, matches in snaps:
        for m in matches:
            for k in _keys(m):
                if m.lan is not None:
                    lan_seen[k] = m.lan
                if m.event_weight is not None:
                    ev_seen[k] = m.event_weight

    chosen: list[Match] = []
    prev_date: date | None = None
    prev_counts: Counter = Counter()
    for snap, matches in snaps:
        late: dict[tuple, list[Match]] = defaultdict(list)
        for m in matches:
            if prev_date is None or m.date > prev_date:
                chosen.append(m)
            elif (prev_date - m.date).days < lag_days:
                late[_keys(m)[0]].append(m)
        for name_key, ms in late.items():
            keys = _keys(ms[0])
            already = max(prev_counts[k] for k in keys)  # copies the previous snapshot had
            chosen.extend(ms[already:])
        prev_date = snap
        prev_counts = Counter(k for m in matches for k in _keys(m))

    out = []
    for m in chosen:
        keys = _keys(m)
        lan = m.lan if m.lan is not None else next((lan_seen[k] for k in keys if k in lan_seen), None)
        ev = m.event_weight if m.event_weight is not None else next((ev_seen[k] for k in keys if k in ev_seen), None)
        out.append(replace(m, lan=lan, event_weight=ev))
    out.sort(key=lambda m: (m.date, m.winner, m.loser))
    return out


def roster_overlap(a: Roster | None, b: Roster | None) -> int:
    if not a or not b:
        return 0
    return len({p.lower() for p in a} & {p.lower() for p in b})
