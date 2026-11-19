"""Step 7c: replay past Major Stage 1s and grade the ballots against what happened.

For each data/events/past/*.json (scripts/build_past_events.py): Model v1
with only the matches before the stage started, and Baseline 0 (VRS points,
Elo scale 1100), each simulated and both ballots chosen as in run_stage.py,
then graded against the real records. Also the record log score: average
-ln P(the record each team actually finished with), lower = better.

Caveats (journal Step 7c): the model's settings were tuned on matches up to
2025-10 (so Shanghai 2024 and Austin 2025 are not out of sample for them),
and the BO3 scale was fitted on all linked matches, test period included.
Budapest 2025 and Cologne 2026 are in the test period: results there must
not be used to change the model.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem import simulate  # noqa: E402
from pickem.ballot import Grader, best_expected, best_threshold, confirm  # noqa: E402
from pickem.baseline import matrices_from_points  # noqa: E402
from pickem.predict import event_matrices, load_model  # noqa: E402
from pickem.simulate import RESULT_ORDER  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CODE = {"3-0": 3, "3-1": 2, "3-2": 1, "2-3": -1, "1-3": -2, "0-3": -3}
SIMS = 50_000


def ballots(teams, p1, p3, seed):
    search = simulate.run(teams, p1, p3, n_sims=SIMS, seed=seed)
    fresh = simulate.run(teams, p1, p3, n_sims=SIMS, seed=seed + 1)
    gs, gf = Grader(search.codes), Grader(fresh.codes)
    a = best_expected(gs)
    b = confirm([x for x, _ in best_threshold(gs, top=20)], gf)[0][0]
    return fresh, gf, a, b


def main():
    bo = json.loads((ROOT / "data/processed/bo_scales.json").read_text(encoding="utf-8"))
    totals = {}
    for path in sorted((ROOT / "data/events/past").glob("*.json"), key=lambda p: json.loads(p.read_text("utf-8"))["start_date"]):
        ev = json.loads(path.read_text(encoding="utf-8"))
        info = sorted(ev["teams"], key=lambda t: t["seed"])
        teams = [t["name"] for t in info]
        on = date.fromisoformat(ev["start_date"])
        actual = np.array([[CODE[ev["actual_records"][t]] for t in teams]], dtype=np.int8)
        g_actual = Grader(actual)
        eng, cfg = load_model(ROOT, before=on)
        m1, m3, states = event_matrices(eng, cfg, info, on, bo3_scale=bo["bo3_scale"])
        b1, b3 = matrices_from_points([t["vrs_points"] for t in info], scale=1100.0)
        print(f"\n=== {ev['event']} {ev['stage']} ({on}) ===")
        missing = [t for t, s in zip(teams, states) if not s["found"]]
        if missing:
            print(f"  no match history for: {', '.join(missing)}")
        adv = {}
        for label, p1, p3 in (("Model v1", m1, m3), ("Baseline 0", b1, b3)):
            fresh, gf, a, b = ballots(teams, p1, p3, seed=2026)
            probs = fresh.probabilities()                      # (16, 6) in RESULT_ORDER
            col = {c: i for i, c in enumerate(RESULT_ORDER)}
            adv[label] = probs[:, [col[3], col[2], col[1]]].sum(axis=1)
            ll = -np.mean([math.log(max(probs[i, col[int(actual[0, i])]], 1e-4)) for i in range(len(teams))])
            for name, ballot in (("A max expected", a), ("B max P(>=5)", b)):
                hit = int(g_actual.hits(ballot)[0])
                pred_e, pred_p = gf.expected(ballot), gf.p_success(ballot)
                print(f"  {label:<10} {name:<15} predicted E = {pred_e:.2f}, P(>=5) = {pred_p:.1%}; "
                      f"ACTUAL correct = {hit}{'  (passed)' if hit >= 5 else ''}")
                key = (label, name)
                t = totals.setdefault(key, [0.0, 0.0, 0, 0])
                t[0] += pred_e
                t[1] += pred_p
                t[2] += hit
                t[3] += hit >= 5
                if name.startswith("B"):
                    print(f"  {'':<10} {'':<15} {ballot.describe(teams)}")
            print(f"  {label:<10} record log score {ll:.3f} (coin-flip-like uniform over 6 records: {math.log(6):.3f})")
            totals.setdefault((label, "ll"), []).append(ll)
        # where the two models disagree most about advancing (region of the matched team, from VRS pages)
        gap = adv["Model v1"] - adv["Baseline 0"]
        print("  biggest disagreements (advance %: Model v1 vs Baseline 0, actual record):")
        for i in np.argsort(-np.abs(gap))[:5]:
            t = eng.teams[eng.find(info[i].get("org_name", info[i]["name"]),
                                   frozenset(p.lower() for p in info[i]["roster"]))[0]] if states[i]["found"] else None
            region = (eng.region_of(t) if t else None) or "?"
            print(f"    seed {i + 1:>2} {teams[i]:<20} {region:<9} {adv['Model v1'][i]:5.1%} vs "
                  f"{adv['Baseline 0'][i]:5.1%}  -> {ev['actual_records'][teams[i]]}")
    n = len(totals.get(("Model v1", "ll"), []))
    print(f"\n=== totals over {n} stages ===")
    for label in ("Model v1", "Baseline 0"):
        for name in ("A max expected", "B max P(>=5)"):
            e, p, hit, passed = totals[(label, name)]
            print(f"  {label:<10} {name:<15} predicted correct {e:.1f}, actual {hit}; "
                  f"predicted passes {p:.2f}, actual {passed}")
        print(f"  {label:<10} mean record log score {np.mean(totals[(label, 'll')]):.3f}")
    # teams in a stage share outcomes, so the stage is the unit: SE from the spread of the stage differences
    d = np.array(totals[("Model v1", "ll")]) - np.array(totals[("Baseline 0", "ll")])
    se = d.std(ddof=1) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    print(f"  record log score, Model v1 minus Baseline 0: {d.mean():+.3f} (SE {se:.3f}, {len(d)} stages; "
          f"negative = Model v1 better)")


if __name__ == "__main__":
    main()
