"""Simulate a Swiss stage and compare the two ways of choosing a ballot.

Usage:
    python scripts/run_stage.py data/events/singapore-2026-stage1.json
    python scripts/run_stage.py EVENT.json --sims 200000 --scale 500

Currently uses Baseline 0 (VRS points -> Elo; see pickem/baseline.py).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem import simulate  # noqa: E402
from pickem.ballot import Grader, best_expected, best_threshold, confirm  # noqa: E402
from pickem.baseline import matrices_from_points  # noqa: E402


def show_ballot(label, ballot, grader, teams):
    dist = grader.distribution(ballot)
    print(f"\n{label}")
    print("  " + ballot.describe(teams))
    print(f"  expected correct = {grader.expected(ballot):.2f}   P(>= {grader.rules.threshold}) = {grader.p_success(ballot):.1%}")
    print("  P(exactly k correct): " + "  ".join(f"{k}:{p:.0%}" for k, p in enumerate(dist) if p >= 0.005))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event", type=Path)
    ap.add_argument("--sims", type=int, default=100_000, help="simulations used to search for ballots")
    ap.add_argument("--confirm-sims", type=int, default=100_000, help="fresh simulations used to re-grade finalists")
    ap.add_argument("--scale", type=float, default=1100.0, help="Elo scale; larger = closer to 50/50 (1100 = fitted on past top-50 matches, Step 5)")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    event = json.loads(args.event.read_text(encoding="utf-8"))
    teams_info = sorted(event["teams"], key=lambda t: t["seed"])
    teams = [t["name"] for t in teams_info]
    p_bo1, p_bo3 = matrices_from_points([t["vrs_points"] for t in teams_info], scale=args.scale)
    name_to_idx = {n: i for i, n in enumerate(teams)}
    fixed = {}
    for m in event.get("completed_matches", []):
        a, b, w = name_to_idx[m["a"]], name_to_idx[m["b"]], name_to_idx[m["winner"]]
        fixed[(min(a, b), max(a, b))] = w

    print(f"{event['event']} - {event['stage']}  [{event.get('status', '')}]")
    print(f"Model: Baseline 0 (VRS points, Elo scale {args.scale:g})\n")

    t0 = time.time()
    search = simulate.run(teams, p_bo1, p_bo3, n_sims=args.sims, seed=args.seed, fixed=fixed)
    fresh = simulate.run(teams, p_bo1, p_bo3, n_sims=args.confirm_sims, seed=args.seed + 1, fixed=fixed)
    print(search.table())
    print(f"(simulation took {time.time() - t0:.1f}s)")

    g_search, g_fresh = Grader(search.codes), Grader(fresh.codes)
    be = best_expected(g_search)
    finalists = [b for b, _ in best_threshold(g_search, top=20)]
    bt, _ = confirm(finalists, g_fresh)[0]

    print("\nAll numbers below are graded on the fresh simulations (not the ones used to search).")
    show_ballot("A) Maximise expected correct picks", be, g_fresh, teams)
    show_ballot(f"B) Maximise P(>= {g_fresh.rules.threshold} correct)", bt, g_fresh, teams)
    if be == bt:
        print("\nBoth objectives chose the same ballot for this stage.")


if __name__ == "__main__":
    main()
