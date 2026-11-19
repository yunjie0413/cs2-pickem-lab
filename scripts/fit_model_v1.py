"""Step 6: tune Model v1, test each factor, compare with the VRS baseline.

Periods (by match date):
  burn-in    before 2024-08-06   ratings warm up; not scored (no VRS snapshot yet)
  train      2024-08-06 .. 2025-05-31   parameters are tuned here
  validation 2025-06-01 .. 2025-10-31   factors are kept or dropped here
  test       2025-11-01 ..              scored only with --final, once, at the end

Scored matches: both teams ranked in the VRS top 100 at the previous
snapshot (tuning); comparisons with Baseline 0 use the top 50, like Step 5.

Usage:
    python scripts/fit_model_v1.py            (tune, test factors, validate; a few minutes)
    python scripts/fit_model_v1.py --final    (also score the test period)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.evaluate import PointsHistory, accuracy, brier, calibration_table, log_loss  # noqa: E402
from pickem.history import load_history  # noqa: E402
from pickem.model_v1 import LN10_400, Engine, Params, fit_logistic  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TRAIN_START, VAL_START, TEST_START = date(2024, 8, 6), date(2025, 6, 1), date(2025, 11, 1)
TUNE_TOP, REPORT_TOP = 100, 50

# Starting search ranges. While the best value sits on the edge of its range
# and one more step outward still improves, the range is extended (the first
# runs kept ending on edges).
GRID = {
    "k": [16, 24, 32, 48, 64, 96],
    "k_new": [1.0, 2.0, 4.0, 8.0, 16.0],
    "decay_days": [90, 180, 365, 730, math.inf],
    "forget_days": [30, 60, 120, 240, math.inf],
    "roster_reset": [0.0, 0.1, 0.2, 0.35, 0.5, 0.75],
    "roster_new": [0.0, 0.25, 0.5, 0.75, 1.0],
    "w_lan": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0],
    "k_region": [0.0, 1.0, 2.0, 4.0, 8.0],
    "vol_rate": [0.0, 0.02, 0.05, 0.1],
    "vol_shrink": [0.02, 0.05, 0.1],
}
BOUNDS = {"k": (1, 1000), "k_new": (1, 100), "decay_days": (1, math.inf), "forget_days": (1, math.inf),
          "roster_reset": (0, 1), "roster_new": (0, 1), "w_lan": (0.05, 20), "k_region": (0, 100),
          "vol_rate": (0, 1), "vol_shrink": (0, 1)}
GEOMETRIC = {"k", "k_new", "decay_days", "forget_days", "w_lan", "k_region", "vol_rate", "vol_shrink"}
FACTOR_PARAMS = {  # parameters frozen when a factor is switched off
    "time_decay": ["decay_days", "forget_days"],
    "roster_reset": ["roster_reset", "roster_new"],
    "lan": ["w_lan"],
    "region": ["k_region"],
    "volatility": ["vol_rate", "vol_shrink"],
}
CLEAR = 2.0  # a factor is kept only if it helps by more than 2 standard errors
MIN_GAIN = 2e-5  # a search step must improve log loss by this much (else flat
                 # directions drift: new_rating once slid to its bound for a 0.00001 gain)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def show(params: Params) -> str:
    return json.dumps({k: (None if v == math.inf else v) for k, v in asdict(params).items()})


class Scorer:
    def __init__(self, h, points: PointsHistory):
        self.h = h
        vrs = []
        for m in h.matches:
            w = points.lookup(m.date, m.winner, m.winner_roster)
            l = points.lookup(m.date, m.loser, m.loser_roster)
            vrs.append((w[0] - l[0], max(w[1], l[1])) if (w and l) else None)
        d = np.array([m.date for m in h.matches])
        ranked = np.array([v is not None for v in vrs])
        rank = np.array([v[1] if v else 10**6 for v in vrs])
        ra = [h.regions.get(m.winner) for m in h.matches]
        rb = [h.regions.get(m.loser) for m in h.matches]
        cross = np.array([a is not None and b is not None and a != b for a, b in zip(ra, rb)])
        self.vfeat = LN10_400 * np.array([v[0] if v else 0.0 for v in vrs])
        self.masks = {}
        for name, lo, hi in [("train", TRAIN_START, VAL_START), ("val", VAL_START, TEST_START),
                             ("trainval", TRAIN_START, TEST_START), ("test", TEST_START, date(2100, 1, 1))]:
            period = (d >= lo) & (d < hi) & ranked
            self.masks[name] = period & (rank <= TUNE_TOP)
            self.masks[name + "_top50"] = period & (rank <= REPORT_TOP)
            self.masks[name + "_cross"] = self.masks[name] & cross
        self.runs = 0
        self._cache: dict[Params, np.ndarray] = {}

    def z(self, params: Params) -> np.ndarray:
        if params not in self._cache:
            self.runs += 1
            eng = Engine(params, self.h.regions)
            self._cache[params] = np.array([p.z for p in eng.run(self.h.inputs)])
        return self._cache[params]

    def per_match(self, params: Params, fit: str, evaluate: str) -> np.ndarray:
        """Log loss of each match in `evaluate`, with the calibration scale fitted on `fit`."""
        z = self.z(params)
        a = fit_logistic(z[self.masks[fit]][:, None])[0]
        return np.logaddexp(0.0, -a * z[self.masks[evaluate]])  # = -ln sigmoid(a z)

    def loss(self, params: Params, period: str) -> float:
        """Average log loss, calibration scale fitted on the same matches (used for tuning)."""
        return float(self.per_match(params, period, period).mean())


def paired(diff: np.ndarray) -> tuple[float, float]:
    """Mean of per-match differences and its standard error.

    Both models are scored on the same matches, so comparing them match by
    match removes most of the noise that comes from which matches happened.
    """
    return float(diff.mean()), float(diff.std(ddof=1) / math.sqrt(len(diff)))


def _beyond(name: str, values: list, cur) -> float | None:
    """One step past the edge of `values` that `cur` sits on (None if not on an edge)."""
    lo, hi = BOUNDS[name]
    geo = name in GEOMETRIC
    if cur == values[-1] and math.isfinite(cur):
        a, b = values[-2], values[-1]
        nxt = b * (b / a) if (geo and a > 0) else b + (b - a)
    elif cur == values[0]:
        a, b = values[0], values[1]
        if geo and a <= 0:
            return None  # 0 means "factor off": nothing below it
        nxt = a * (a / b) if (geo and math.isfinite(b)) else a - (b - a)
    else:
        return None
    nxt = min(max(nxt, lo), hi)
    return None if nxt in values else nxt


def tune(sc: Scorer, start: Params, period: str, frozen: set[str], rounds: int = 2) -> tuple[Params, float]:
    """Coordinate search: one parameter at a time over its range, repeated."""
    best, best_loss = start, sc.loss(start, period)
    grid = {k: list(v) for k, v in GRID.items()}
    for _ in range(rounds):
        improved = False
        for name, values in grid.items():
            if name in frozen:
                continue
            for v in values:
                if v == getattr(best, name):
                    continue
                cand = replace(best, **{name: v})
                loss = sc.loss(cand, period)
                if loss < best_loss - MIN_GAIN:
                    best, best_loss, improved = cand, loss, True
            while (nxt := _beyond(name, values, getattr(best, name))) is not None:
                if getattr(best, name) == values[-1]:
                    values.append(nxt)
                else:
                    values.insert(0, nxt)
                cand = replace(best, **{name: nxt})
                loss = sc.loss(cand, period)
                if loss >= best_loss - MIN_GAIN:
                    break
                best, best_loss, improved = cand, loss, True
        if not improved:
            break
    return best, best_loss


def compare(sc: Scorer, params: Params, fit: str, evaluate: str, title: str):
    """Baseline 0 vs Model v1 on `evaluate`, everything fitted on `fit`. Returns blend weights."""
    z = sc.z(params)
    X = np.column_stack([z, sc.vfeat])
    f, e = sc.masks[fit], sc.masks[evaluate]
    w_vrs = fit_logistic(sc.vfeat[f][:, None])
    w_own = fit_logistic(z[f][:, None])
    w_blend = fit_logistic(X[f])
    p_vrs = sigmoid(w_vrs[0] * sc.vfeat[e])
    p_own = sigmoid(w_own[0] * z[e])
    p_blend = sigmoid(X[e] @ w_blend)
    print(f"\n{title} ({e.sum():,} matches, both teams VRS top {REPORT_TOP})")
    print(f"    {'model':<34}{'log loss':>9}{'Brier':>8}{'accuracy':>10}")
    for label, p in [("coin flip", np.full(e.sum(), 0.5)),
                     ("Baseline 0: VRS points, refitted", p_vrs),
                     ("Model v1: own rating only", p_own),
                     ("Model v1: own rating + VRS blend", p_blend)]:
        print(f"    {label:<34}{log_loss(p):>9.4f}{brier(p):>8.4f}{accuracy(p):>10.1%}")
    print(f"    blend weights: own rating {w_blend[0]:.3f}, VRS {w_blend[1]:.3f}")
    ll = lambda p: -np.log(np.clip(p, 1e-12, 1))
    for label, p in [("own rating only", p_own), ("own rating + VRS blend", p_blend)]:
        gain, se = paired(ll(p_vrs) - ll(p))
        print(f"    better than Baseline 0 by ({label}): {gain:+.4f} +/- {se:.4f} per match")
    print("    calibration of the blend (favourite's view):")
    for pm, ob, n in calibration_table(p_blend):
        print(f"      predicted {pm:6.1%}   observed {ob:6.1%}   n={n}")
    return w_blend


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="also score the test period (do this once, at the end)")
    args = ap.parse_args()
    t0 = time.time()
    h = load_history(ROOT)
    sc = Scorer(h, PointsHistory(ROOT / "data/processed/vrs_points.csv"))
    print(f"matches {len(h.matches):,}; scored (both VRS top {TUNE_TOP}): "
          f"train {sc.masks['train'].sum():,}, val {sc.masks['val'].sum():,} "
          f"(cross-region {sc.masks['val_cross'].sum():,}), test {sc.masks['test'].sum():,}")
    if h.links:
        print(f"HLTV: {h.hltv_series:,} LAN series, {len(h.links):,} linked to Valve matches "
              f"(train {int(sum(sc.masks['train'][i] for i in h.links))}, "
              f"val {int(sum(sc.masks['val'][i] for i in h.links))} of the scored ones)")
    else:
        print("HLTV: no file, so LAN weighting is not tested")
    no_lan = set() if h.links else {"w_lan"}

    # 1. Tune every parameter on the training period.
    full, train_loss = tune(sc, Params(), "train", frozen=no_lan)
    val_full = float(sc.per_match(full, "train", "val").mean())
    print(f"\n[1] all factors, tuned on train: train {train_loss:.4f}, val {val_full:.4f}  "
          f"({sc.runs} runs, {time.time() - t0:.0f}s)")
    print("    " + show(full))

    # 2. Ablation: switch each factor off, re-tune the rest on train, compare
    #    match by match on all validation matches (calibration scale fitted on
    #    train), as decision 0005 says. For region, the gain on cross-region
    #    matches alone (most of a Major) is printed too, for information: with
    #    under 300 such matches it is too noisy to decide on.
    print(f"\n[2] factor tests on validation. gain = log loss without minus with "
          f"(positive = factor helps); kept only if gain > {CLEAR:g} standard errors:")
    keep = []
    for factor, names in FACTOR_PARAMS.items():
        if factor == "lan" and not h.links:
            print(f"    {factor:<13} not tested (no HLTV file)")
            continue
        if full.without(factor) == full:
            print(f"    {factor:<13} tuning already switched it off -> not used")
            continue
        off, _ = tune(sc, full.without(factor), "train", frozen=set(names) | no_lan, rounds=1)
        gain, se = paired(sc.per_match(off, "train", "val") - sc.per_match(full, "train", "val"))
        if gain > CLEAR * se:
            verdict = "KEEP (clear gain)"
            keep.append(factor)
        elif gain < -CLEAR * se:
            verdict = "drop (it makes predictions worse)"
        else:
            verdict = "drop (no clear effect)"
        print(f"    {factor:<13} gain = {gain:+.4f} +/- {se:.4f}   {verdict}")
        if factor == "region":
            g_x, se_x = paired(sc.per_match(off, "train", "val_cross") - sc.per_match(full, "train", "val_cross"))
            print(f"    {'':<13} (cross-region matches only, n={sc.masks['val_cross'].sum()}: "
                  f"{g_x:+.4f} +/- {se_x:.4f})")

    # 3. Selected factors only, re-tuned on train, checked on validation.
    selected, frozen = full, set(no_lan)
    for factor, names in FACTOR_PARAMS.items():
        if factor not in keep:
            selected = selected.without(factor)
            frozen |= set(names)
    selected, _ = tune(sc, selected, "train", frozen=frozen, rounds=1)
    print(f"\n[3] selected model (kept: {', '.join(keep) or 'none'}), tuned on train:")
    print("    " + show(selected))
    compare(sc, selected, "train", "val_top50", "    VALIDATION")

    # 4. Final model: re-tuned on train + validation; blend fitted there; saved.
    final, tv_loss = tune(sc, selected, "trainval", frozen=frozen, rounds=1)
    z = sc.z(final)
    w_blend = fit_logistic(np.column_stack([z, sc.vfeat])[sc.masks["trainval"]])
    print(f"\n[4] final model, tuned on train+val ({tv_loss:.4f}):")
    print("    " + show(final))
    out = ROOT / "data/processed/model_v1.json"
    out.write_text(json.dumps({
        "params": {k: (None if v == math.inf else v) for k, v in asdict(final).items()},
        "kept_factors": keep,
        "blend": {"own": float(w_blend[0]), "vrs": float(w_blend[1])},
        "hltv_links": len(h.links),
        "fitted_on": f"{TRAIN_START} to {TEST_START} (exclusive), both teams VRS top {TUNE_TOP}",
    }, indent=2), encoding="utf-8")
    print(f"    saved {out.relative_to(ROOT)} (blend weights own {w_blend[0]:.3f}, VRS {w_blend[1]:.3f})")

    # 5. The test period, once.
    if args.final:
        compare(sc, final, "trainval", "test_top50", "[5] TEST")
    else:
        print("\n[5] test period not scored (run with --final once the model is settled)")
    print(f"\n({sc.runs} engine runs, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
