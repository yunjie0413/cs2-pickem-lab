"""Everything the rating engine reads, assembled in one place.

Valve's match list (data/processed/matches.csv) plus, when the local HLTV
file exists, which of those matches were LAN matches between top-50 teams
(data/raw/hltv/maps_lan_top50.csv, linked by date and team names).

Valve's own LAN flags and event weights are NOT passed on: they are shown
only for a team's "ten best" wins, a list that depends on results after
the match (docs/JOURNAL.md Step 6, decision 0006).
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .data.hltv import Series, group_series, link_series, load_maps
from .data.hltv_players import PlayerRatings, load_players
from .evaluate import load_matches
from .model_v1 import MatchIn

HLTV_FILE = "data/raw/hltv/maps_lan_top50.csv"
PLAYERS_FILE = "data/raw/hltv/players_monthly.csv"


@dataclass
class History:
    matches: list                 # MatchRecord rows from matches.csv, in date order
    inputs: list[MatchIn]         # the same matches as the engine reads them
    regions: dict[str, str]       # team name -> VRS region (most frequent)
    links: dict[int, Series]      # match index -> HLTV series (LAN, both teams HLTV top 50)
    hltv_series: int              # series in the HLTV file (0 = no file used)
    players: PlayerRatings | None = None  # HLTV player ratings by month (None = no file)


def load_regions(root: Path) -> dict[str, str]:
    counts: dict[str, Counter] = {}
    with open(root / "data/processed/vrs_points.csv", newline="", encoding="utf-8") as fp:
        for r in csv.DictReader(fp):
            if r["region"]:
                counts.setdefault(r["team"], Counter())[r["region"]] += 1
    return {t: c.most_common(1)[0][0] for t, c in counts.items()}


def load_history(root: Path, use_hltv: bool = True) -> History:
    matches = load_matches(root / "data/processed/matches.csv")
    links: dict[int, Series] = {}
    n_series = 0
    path = root / HLTV_FILE
    if use_hltv and path.exists():
        series = group_series(load_maps(path))
        n_series = len(series)
        links = link_series(series, matches)
    inputs = [MatchIn(m.date, m.winner, m.loser, m.winner_roster, m.loser_roster, True if i in links else None)
              for i, m in enumerate(matches)]
    ppath = root / PLAYERS_FILE
    players = load_players(ppath) if (use_hltv and ppath.exists()) else None
    return History(matches, inputs, load_regions(root), links, n_series, players)
