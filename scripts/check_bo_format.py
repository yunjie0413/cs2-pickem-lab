"""Step 6b: are BO1s more random than BO3s, and by how much?

Valve's data never says whether a match was BO1 or BO3. HLTV's map list
does (1 map = BO1, 2-3 maps = BO3); pickem/history.py links each HLTV
series to the same match in Valve's data. Here Model v1's pre-match
predictions on those linked matches (LAN, both teams HLTV top 50) are
split by format.

Questions answered:
  1. What calibration scale fits BO1s, and BO3s? The model's probability
     is sigmoid(scale x blend); scale 1.0 = as fitted on all of Valve's
     matches (all formats, mostly online).
  2. Does "independent maps" hold? If a team wins a BO3 with q, its map
     chance p solves p^2 (3 - 2p) = q, and it should win a BO1 with p.

The two scales are saved to data/processed/bo_scales.json for
scripts/run_stage.py. They are fitted on all linked matches (2024-12 on,
after a warm-up), test period included: a calibration, not a test result.

Usage:
    python scripts/check_bo_format.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.baseline import map_from_bo3  # noqa: E402
from pickem.evaluate import PointsHistory, log_loss  # noqa: E402
from pickem.history import load_history  # noqa: E402
from pickem.model_v1 import LN10_400, Engine, fit_logistic  # noqa: E402
from pickem.predict import load_config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def scale_se(x: np.ndarray, a: float) -> float:
    """Standard error of a fitted scale (inverse Fisher information)."""
    s = 1 / (1 + np.exp(-a * x))
    return float(1 / math.sqrt((s * (1 - s) * x * x).sum()))


def main():
    params, cfg = load_config(ROOT)
    h = load_history(ROOT, use_hltv=True)
    if not h.links:
        sys.exit("no HLTV links: put the HLTV map file at data/raw/hltv/maps_lan_top50.csv")
    if cfg.get("hltv_links", 0) == 0:
        print("note: model_v1.json was fitted without HLTV; re-run scripts/fit_model_v1.py first\n")
    eng = Engine(params, h.regions, h.players)
    z = np.array([p.z for p in eng.run(h.inputs)])
    ph = PointsHistory(ROOT / "data/processed/vrs_points.csv")
    n_maps = sum(len(s.maps) for s in h.links.values())
    print(f"HLTV series {h.hltv_series:,}; linked to Valve matches {len(h.links):,} ({n_maps:,} maps)")

    start = h.matches[0].date + timedelta(days=180)  # ratings start from scratch: skip a warm-up
    rows = []
    for i, s in h.links.items():
        m = h.matches[i]
        w = ph.lookup(m.date, m.winner, m.winner_roster)
        l = ph.lookup(m.date, m.loser, m.loser_roster)
        if m.date < start or not (w and l):
            continue
        rows.append((cfg["blend"]["own"] * z[i] + cfg["blend"]["vrs"] * LN10_400 * (w[0] - l[0]), s.best_of))
    x = np.array([r[0] for r in rows])
    bo = np.array([r[1] for r in rows])
    print(f"with VRS points for both teams: {len(x):,}  (by best-of: {dict(sorted(Counter(bo.tolist()).items()))})\n")

    x1, x3 = x[bo == 1], x[bo == 3]
    a_all = fit_logistic(x[bo != 5][:, None])[0]
    a1 = fit_logistic(x1[:, None])[0]
    a3 = fit_logistic(x3[:, None])[0]
    print("calibration scale on these LAN matches (1.0 = the all-match fit):")
    print(f"  BO1 and BO3 together : {a_all:.3f} +/- {scale_se(x[bo != 5], a_all):.3f}")
    print(f"  BO1 only             : {a1:.3f} +/- {scale_se(x1, a1):.3f}   (n={len(x1):,})")
    print(f"  BO3 only             : {a3:.3f} +/- {scale_se(x3, a3):.3f}   (n={len(x3):,})")

    p_indep = np.array([map_from_bo3(q) for q in 1 / (1 + np.exp(-a3 * x1))])
    print(f"\nBO1 matches, log loss of four ways to predict them:")
    print(f"  scale 1.0 (the all-match fit; what the simulator used)  {log_loss(1 / (1 + np.exp(-x1))):.4f}")
    print(f"  one LAN scale for both formats                         {log_loss(1 / (1 + np.exp(-a_all * x1))):.4f}")
    print(f"  BO1's own scale                                        {log_loss(1 / (1 + np.exp(-a1 * x1))):.4f}")
    print(f"  from BO3's scale, assuming independent maps            {log_loss(p_indep):.4f}")
    print(f"BO3 matches:")
    print(f"  scale 1.0                                              {log_loss(1 / (1 + np.exp(-x3))):.4f}")
    print(f"  one LAN scale for both formats                         {log_loss(1 / (1 + np.exp(-a_all * x3))):.4f}")
    print(f"  BO3's own scale                                        {log_loss(1 / (1 + np.exp(-a3 * x3))):.4f}")

    for q in (0.60, 0.70):
        xq = math.log(q / (1 - q)) / a3
        p1 = 1 / (1 + math.exp(-a1 * xq))
        print(f"\nA team that wins a BO3 {q:.0%} of the time wins a BO1 {p1:.1%} of the time "
              f"(independent maps would say {map_from_bo3(q):.1%}).")

    # Used by the simulator: BO3's scale (2,000+ matches), and BO1 derived from
    # the BO3 probability by independent maps, which fits past BO1s as well as
    # their own scale (fitted on only ~300 BO1s, so much noisier).
    out = ROOT / "data/processed/bo_scales.json"
    out.write_text(json.dumps({
        "bo3_scale": float(a3), "bo3_se": scale_se(x3, a3), "n_bo3": int(len(x3)),
        "bo1_rule": "independent maps from the BO3 probability",
        "bo1_scale_fitted": float(a1), "bo1_se": scale_se(x1, a1), "n_bo1": int(len(x1)),
        "bo1_log_loss": {"own_scale": log_loss(1 / (1 + np.exp(-a1 * x1))),
                         "independent_maps": log_loss(p_indep)},
    }, indent=2), encoding="utf-8")
    print(f"\nsaved {out.relative_to(ROOT)}: BO3 scale {a3:.3f}; BO1 from BO3 by independent maps")


if __name__ == "__main__":
    main()
