"""Build the match history and VRS points history from Valve's VRS snapshots.

Usage:
    python scripts/fetch_vrs.py          # once: downloads data/raw/vrs
    python scripts/build_matches.py

Writes:
    data/processed/matches.csv     one row per match (deduplicated)
    data/processed/vrs_points.csv  every roster's VRS points at every snapshot
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.data import vrs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def fmt_roster(r):
    return "" if r is None else ";".join(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vrs", type=Path, default=ROOT / "data/raw/vrs")
    ap.add_argument("--out", type=Path, default=ROOT / "data/processed")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    per_snapshot = []
    with open(args.out / "vrs_points.csv", "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["snapshot", "team", "roster", "global_rank", "region", "points"])
        for snap, folder in vrs.snapshot_dirs(args.vrs):
            pages = vrs.load_snapshot(folder, snap)
            for p in pages:
                w.writerow([snap, p.team, fmt_roster(p.roster), p.global_rank or "", p.region or "", p.points or ""])
            per_snapshot.append((snap, vrs.matches_in_snapshot(pages)))
            print(f"  {snap}: {len(pages)} rosters", file=sys.stderr)

    history = vrs.build_history(per_snapshot)
    with open(args.out / "matches.csv", "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["date", "winner", "loser", "winner_roster", "loser_roster", "lan", "event_weight", "snapshot"])
        for m in history:
            lan = "" if m.lan is None else int(m.lan)
            ev = "" if m.event_weight is None else m.event_weight
            w.writerow([m.date, m.winner, m.loser, fmt_roster(m.winner_roster), fmt_roster(m.loser_roster), lan, ev, m.snapshot])

    n = len(history)
    lan = Counter(m.lan for m in history)
    both_rosters = sum(m.winner_roster is not None and m.loser_roster is not None for m in history)
    print(f"snapshots: {len(per_snapshot)} ({per_snapshot[0][0]} .. {per_snapshot[-1][0]})")
    print(f"matches: {n:,}  dates {history[0].date} .. {history[-1].date}")
    print(f"LAN known: {(lan[True] + lan[False]) / n:.0%}  (LAN {lan[True]:,}, online {lan[False]:,}, unknown {lan[None]:,})")
    print(f"event weight known: {sum(m.event_weight is not None for m in history) / n:.0%}")
    print(f"both lineups known: {both_rosters / n:.0%}")


if __name__ == "__main__":
    main()
