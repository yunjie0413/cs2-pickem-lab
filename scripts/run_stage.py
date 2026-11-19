"""Simulate a Swiss stage and compare the two ways of choosing a ballot.

Usage:
    python scripts/run_stage.py data/events/singapore-2026-stage1.json              (Model v1)
    python scripts/run_stage.py EVENT.json --model baseline --scale 1100            (Baseline 0)

Model v1 needs data/processed/model_v1.json (scripts/fit_model_v1.py) and
uses data/processed/bo_scales.json (scripts/check_bo_format.py) if present.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem import simulate  # noqa: E402
from pickem.ballot import Grader, best_expected, best_threshold, confirm  # noqa: E402
from pickem.baseline import matrices_from_points  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


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
    ap.add_argument("--model", choices=["v1", "baseline"], default="v1")
    ap.add_argument("--scale", type=float, default=1100.0, help="Baseline 0 only: Elo scale (1100 = fitted in Step 5)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--sigma", type=float, default=None,
                    help="Model v1 only: spread of each team's strength per simulated stage (blend-logit units; "
                         "default: data/processed/uncertainty.json, 0 if absent)")
    ap.add_argument("--no-recent", action="store_true",
                    help="Model v1 only: ignore HLTV results newer than Valve's match list (Step 9b)")
    args = ap.parse_args()

    event = json.loads(args.event.read_text(encoding="utf-8"))
    teams_info = sorted(event["teams"], key=lambda t: t["seed"])
    teams = [t["name"] for t in teams_info]
    sampler = None
    if args.model == "baseline":
        p_bo1, p_bo3 = matrices_from_points([t["vrs_points"] for t in teams_info], scale=args.scale)
        model_label = f"Baseline 0 (VRS points, Elo scale {args.scale:g})"
    else:
        from pickem.predict import event_matrices, load_model
        eng, cfg = load_model(ROOT, recent_for=None if args.no_recent else teams_info)
        bo_path = ROOT / "data/processed/bo_scales.json"
        bo = json.loads(bo_path.read_text(encoding="utf-8")) if bo_path.exists() else {"bo3_scale": 1.0}
        on = date.fromisoformat(event.get("start_date", date.today().isoformat()))
        p_bo1, p_bo3, states = event_matrices(eng, cfg, teams_info, on, bo3_scale=bo["bo3_scale"])
        missing = [t["name"] for t, s in zip(teams_info, states) if not s["found"]]
        kept = ", ".join(cfg.get("kept_factors", [])) or "none"
        sigma = args.sigma
        u_path = ROOT / "data/processed/uncertainty.json"
        if sigma is None:
            sigma = json.loads(u_path.read_text(encoding="utf-8"))["sigma"] if u_path.exists() else 0.0
        model_label = (f"Model v1 (own rating, factors kept: {kept}; VRS blend; BO3 scale {bo['bo3_scale']:.2f}"
                       f"{'' if bo_path.exists() else ' (NOT fitted: no HLTV data)'}; "
                       f"BO1 from BO3 by independent maps; strength spread per stage sigma = {sigma:g})")
        if sigma > 0:
            from pickem.predict import event_logits
            from pickem.uncertainty import make_sampler, marginal_check
            logit, _ = event_logits(eng, cfg, teams_info, on)
            sampler = make_sampler(logit, bo["bo3_scale"], sigma)
            d1, d3 = marginal_check(logit, bo["bo3_scale"], sigma)
            model_label += (f"\n  single-match probabilities averaged over the strength draws differ from the "
                            f"fixed ones by at most {d1:.3f} (BO1) / {d3:.3f} (BO3)")
        rec = cfg.get("recent")
        if rec is not None:
            model_label += (f"\n  HLTV results newer than Valve's match list: {len(rec.inputs)} matches used, "
                            f"{len(rec.skipped)} skipped")
            for line in rec.skipped:
                model_label += f"\n    skipped: {line}"
        if missing:
            model_label += f"\n  WARNING: no match history found for {', '.join(missing)}"
        model_label += "\n  team ratings (matched in Valve's data as / matches played / last match):"
        for t, s in zip(teams_info, states):
            if s["found"]:
                model_label += (f"\n    {t['name']:<20} {s['rating']:7.0f}  as {s['matched_as']!r}, "
                                f"{s['played']} matches, last {s['last_match']}")
                if s.get("joined") or s.get("left"):
                    model_label += (f"\n    {'':<20} lineup differs from its last match: in "
                                    f"{', '.join(s['joined']) or '-'}, out {', '.join(s['left']) or '-'} "
                                    f"({s['roster_adj']:+.0f} rating from player ratings)")
    name_to_idx = {n: i for i, n in enumerate(teams)}
    fixed = {}
    for m in event.get("completed_matches", []):
        a, b, w = name_to_idx[m["a"]], name_to_idx[m["b"]], name_to_idx[m["winner"]]
        fixed[(min(a, b), max(a, b))] = w

    print(f"{event['event']} - {event['stage']}  [{event.get('status', '')}]")
    print(f"Model: {model_label}\n")

    t0 = time.time()
    search = simulate.run(teams, p_bo1, p_bo3, n_sims=args.sims, seed=args.seed, fixed=fixed, sampler=sampler)
    fresh = simulate.run(teams, p_bo1, p_bo3, n_sims=args.confirm_sims, seed=args.seed + 1, fixed=fixed,
                         sampler=sampler)
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
