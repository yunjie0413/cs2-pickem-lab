"""Recent results from HLTV, for matches newer than Valve's match list (Step 9b).

Valve publishes its match list once a month with each VRS snapshot. The
newest one before the Singapore Major (2026-11-02) ends on 2026-11-01, so
three weeks of results were missing. HLTV's results pages for the Stage 1
teams, collected in the user's Chrome, fill that gap. The file
(data/raw/hltv/results_recent.csv) stays on the user's PC, like all HLTV data.

One row per (Stage 1 team page, match):
    event_team  the Stage 1 team (event-file name) whose page listed the match
    utc         match time, ISO 8601 UTC
    team1, team2, score ("2-1" for a series, round score for a BO1)
    fmt         "bo3", "bo5", or the map name for a BO1
    event, match_id (HLTV)

A match between two Stage 1 teams is listed on both pages; it counts once.
Stage 1 teams play with their event-file lineups. Opponents are found by
name in Valve's match list (HLTV names learned from linked LAN series, or
the same name after normalising); matches against teams Valve's list
doesn't know are skipped and reported.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from ..model_v1 import MatchIn
from .hltv import norm_name


@dataclass
class Recent:
    inputs: list[MatchIn]                  # in time order, side A = winner
    used: list[str] = field(default_factory=list)      # one line per match used
    skipped: list[str] = field(default_factory=list)   # one line per match skipped, with the reason


def load_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def hltv_to_valve_names(links: dict, matches: list) -> dict[str, str]:
    """HLTV team name -> Valve name, from series already linked to Valve's matches."""
    votes: dict[str, Counter] = defaultdict(Counter)
    for i, s in links.items():
        votes[s.team_a][matches[i].winner] += 1
        votes[s.team_b][matches[i].loser] += 1
    return {h: c.most_common(1)[0][0] for h, c in votes.items()}


def recent_inputs(rows: list[dict], teams: list[dict], name_map: dict[str, str], valve_names: set[str],
                  after: date) -> Recent:
    """MatchIn records for matches after `after`. teams: event-file entries."""
    by_event = {t["name"]: t for t in teams}
    by_norm = {}
    for n in valve_names:
        by_norm.setdefault(norm_name(n), n)

    # Each Stage 1 team's HLTV name: the side present in every row of its page
    pages: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        pages[r["event_team"]].append(r)
    hltv_name: dict[str, str] = {}
    for team, rs in pages.items():
        common = set.intersection(*({r["team1"], r["team2"]} for r in rs))
        if len(common) > 1:  # a single row: pick the side that looks like the team
            t = by_event[team]
            want = {norm_name(t["name"]), norm_name(t.get("org_name", t["name"]))}
            common = {c for c in common if norm_name(c) in want or norm_name(name_map.get(c, "")) in want} or common
        if len(common) == 1:
            hltv_name[next(iter(common))] = team

    def side(name: str):
        """(Valve name, lineup) or None if the team is unknown to Valve's list."""
        if name in hltv_name:
            t = by_event[hltv_name[name]]
            return t.get("org_name", t["name"]), t["roster"]
        valve = name_map.get(name) or by_norm.get(norm_name(name))
        return (valve, None) if valve else None

    out = Recent([])
    seen = set()
    for r in sorted(rows, key=lambda r: r["utc"]):
        if r["match_id"] in seen:
            continue
        seen.add(r["match_id"])
        when = datetime.fromisoformat(r["utc"].replace("Z", "+00:00"))
        d = when.date()
        label = f"{d} {r['team1']} {r['score']} {r['team2']} ({r['fmt']}, {r['event']})"
        if d <= after:
            continue
        try:
            a, b = (int(x) for x in r["score"].split("-"))
        except ValueError:
            out.skipped.append(f"{label}: unreadable score")
            continue
        if a == b:
            out.skipped.append(f"{label}: no winner")
            continue
        s1, s2 = side(r["team1"]), side(r["team2"])
        if s1 is None or s2 is None:
            unknown = r["team1"] if s1 is None else r["team2"]
            out.skipped.append(f"{label}: {unknown} not in Valve's match list")
            continue
        (wn, wl), (ln, ll) = (s1, s2) if a > b else (s2, s1)
        out.inputs.append(MatchIn(d, wn, ln, wl, ll, None))
        out.used.append(label)
    return out
