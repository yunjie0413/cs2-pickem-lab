"""Build event files for past Major Stage 1s (Step 7c backtest).

Seeds and final records: Liquipedia, read 2026-11-19 in the user's Chrome.
For each stage the seed order is the order of the stage's invite list on the
event's main page; it matches every round-1 pairing (seed i vs i + 8) on
the stage page. Lineups: each team's first match of the stage in Valve's
data. VRS points: the last snapshot before the stage (as for Singapore).

Writes data/events/past/<key>.json (same format as the Singapore file, plus
"actual_records").
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.evaluate import PointsHistory, load_matches  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Liquipedia name -> name in Valve's data, where they differ
VALVE_NAME = {
    "Team Liquid": "Liquid", "FURIA Esports": "FURIA", "paiN Gaming": "paiN", "Imperial Esports": "Imperial",
    "Fnatic": "fnatic", "Lynn Vision Gaming": "Lynn Vision", "BetBoom Team": "BetBoom", "Nemiga Gaming": "Nemiga",
    "FaZe Clan": "FaZe", "The Huns Esports": "The Huns", "THUNDERdOWNUNDER": "THUNDER dOWNUNDER",
    "Sharks Esports": "Sharks", "SINNERS Esports": "SINNERS",
}

STAGES = {
    "shanghai-2024-opening": {
        "event": "Perfect World Shanghai Major 2024", "stage": "Opening Stage",
        "start": date(2024, 11, 30), "end": date(2024, 12, 3),
        "seeding": "Valve Regional Standings within each region's pre-defined seeds (Liquipedia)",
        "seeds": ["FURIA Esports", "Virtus.pro", "Team Liquid", "Complexity", "BIG", "Fnatic", "The MongolZ",
                  "paiN Gaming", "GamerLegion", "MIBR", "Cloud9", "FlyQuest", "Passion UA", "Wildcard",
                  "Rare Atom", "Imperial Esports"],
        "records": {"The MongolZ": "3-0", "Team Liquid": "3-0", "GamerLegion": "3-1", "FURIA Esports": "3-1",
                    "paiN Gaming": "3-1", "Wildcard": "3-2", "BIG": "3-2", "MIBR": "3-2", "FlyQuest": "2-3",
                    "Passion UA": "2-3", "Complexity": "2-3", "Virtus.pro": "1-3", "Cloud9": "1-3",
                    "Rare Atom": "1-3", "Imperial Esports": "0-3", "Fnatic": "0-3"},
    },
    "austin-2025-stage1": {
        "event": "BLAST.tv Austin Major 2025", "stage": "Stage 1",
        "start": date(2025, 6, 3), "end": date(2025, 6, 6),
        "seeding": "Valve Global Standings (Liquipedia)",
        "seeds": ["Complexity", "HEROIC", "B8", "BetBoom Team", "TYLOO", "Lynn Vision Gaming", "Wildcard", "FlyQuest",
                  "OG", "Chinggis Warriors", "Imperial Esports", "Nemiga Gaming", "NRG", "Legacy", "Metizport",
                  "Fluxo"],
        "records": {"B8": "3-0", "HEROIC": "3-0", "BetBoom Team": "3-1", "OG": "3-1", "Nemiga Gaming": "3-1",
                    "Lynn Vision Gaming": "3-2", "Legacy": "3-2", "TYLOO": "3-2", "FlyQuest": "2-3", "NRG": "2-3",
                    "Wildcard": "2-3", "Imperial Esports": "1-3", "Chinggis Warriors": "1-3", "Complexity": "1-3",
                    "Metizport": "0-3", "Fluxo": "0-3"},
    },
    "budapest-2025-stage1": {
        "event": "StarLadder Budapest Major 2025", "stage": "Stage 1",
        "start": date(2025, 11, 24), "end": date(2025, 11, 27),
        "seeding": "Valve Global Standings (Liquipedia)",
        "seeds": ["Legacy", "FaZe Clan", "B8", "GamerLegion", "Fnatic", "PARIVISION", "Ninjas in Pyjamas",
                  "Imperial Esports", "FlyQuest", "Lynn Vision Gaming", "M80", "Fluxo", "RED Canids",
                  "The Huns Esports", "NRG", "Rare Atom"],
        "records": {"M80": "3-0", "FlyQuest": "3-0", "B8": "3-1", "Fnatic": "3-1", "Ninjas in Pyjamas": "3-1",
                    "PARIVISION": "3-2", "Imperial Esports": "3-2", "FaZe Clan": "3-2", "NRG": "2-3",
                    "Fluxo": "2-3", "Legacy": "2-3", "The Huns Esports": "1-3", "RED Canids": "1-3",
                    "GamerLegion": "1-3", "Lynn Vision Gaming": "0-3", "Rare Atom": "0-3"},
    },
    "cologne-2026-stage1": {
        "event": "IEM Cologne Major 2026", "stage": "Stage 1",
        "start": date(2026, 6, 2), "end": date(2026, 6, 5),
        "seeding": "Valve Global Standings (Liquipedia)",
        "seeds": ["GamerLegion", "B8", "HEROIC", "BetBoom Team", "BIG", "M80", "MIBR", "SINNERS Esports", "NRG",
                  "TYLOO", "Sharks Esports", "Gaimin Gladiators", "Team Liquid", "Lynn Vision Gaming",
                  "THUNDERdOWNUNDER", "FlyQuest"],
        "records": {"B8": "3-0", "BetBoom Team": "3-0", "GamerLegion": "3-1", "M80": "3-1", "MIBR": "3-1",
                    "TYLOO": "3-2", "BIG": "3-2", "FlyQuest": "3-2", "Team Liquid": "2-3", "NRG": "2-3",
                    "Lynn Vision Gaming": "2-3", "THUNDERdOWNUNDER": "1-3", "Sharks Esports": "1-3",
                    "HEROIC": "1-3", "Gaimin Gladiators": "0-3", "SINNERS Esports": "0-3"},
    },
}


def main():
    matches = load_matches(ROOT / "data/processed/matches.csv")
    points = PointsHistory(ROOT / "data/processed/vrs_points.csv")
    out_dir = ROOT / "data/events/past"
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, st in STAGES.items():
        window = [m for m in matches if st["start"] - timedelta(days=1) <= m.date <= st["end"] + timedelta(days=1)]
        teams, problems = [], []
        for seed, name in enumerate(st["seeds"], start=1):
            vname = VALVE_NAME.get(name, name)
            roster = next((list(m.winner_roster if m.winner == vname else m.loser_roster)
                           for m in window if vname in (m.winner, m.loser)
                           and (m.winner_roster if m.winner == vname else m.loser_roster)), None)
            if roster is None:
                problems.append(f"{name}: no stage match in Valve's data")
            vrs = points.lookup(st["start"], vname, roster)
            if vrs is None:
                problems.append(f"{name}: not in the VRS snapshot")
            teams.append({"seed": seed, "name": name, "org_name": vname, "roster": roster or [],
                          "vrs_points": vrs[0] if vrs else 0, "vrs_global_rank": vrs[1] if vrs else None})
        ev = {"event": st["event"], "stage": st["stage"], "start_date": st["start"].isoformat(),
              "status": "PAST STAGE (backtest): seeds and records from Liquipedia, read 2026-11-19",
              "seeding_method": st["seeding"], "teams": teams, "completed_matches": [],
              "actual_records": {t: r for t, r in st["records"].items()}}
        (out_dir / f"{key}.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{key}: {len(teams)} teams" + ("; PROBLEMS: " + "; ".join(problems) if problems else ", all found"))


if __name__ == "__main__":
    main()
