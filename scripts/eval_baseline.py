"""Step 5: how well do Valve's VRS points predict past matches?

For every match, each team's points come from the latest VRS snapshot
strictly before the match (no peeking at the future). The prediction is
the Elo curve P = 1 / (1 + 10^(-gap/scale)).

We fit `scale` on older matches (training period) and report results on
newer ones (test period) that played no part in the fitting.

Usage:
    python scripts/eval_baseline.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pickem.evaluate import PointsHistory, calibration_table, load_matches, log_loss, summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPLIT = date(2025, 11, 1)  # train: before this date; test: on/after
TOP = 50                   # "tier-1-ish": both teams in the global top 50 at the time


def elo(gap: np.ndarray, scale: float) -> np.ndarray:
    return 1.0 / (1.0 + 10.0 ** (-gap / scale))


def main():
    matches = load_matches(ROOT / "data/processed/matches.csv")
    points = PointsHistory(ROOT / "data/processed/vrs_points.csv")

    rows = []  # (date, gap winner-loser, max rank, lan)
    missing = 0
    for m in matches:
        w = points.lookup(m.date, m.winner, m.winner_roster)
        l = points.lookup(m.date, m.loser, m.loser_roster)
        if w is None or l is None:
            missing += 1
            continue
        rows.append((m.date, w[0] - l[0], max(w[1], l[1]), m.lan))
    print(f"matches: {len(matches):,}; both teams ranked at the previous snapshot: {len(rows):,} "
          f"({missing:,} skipped: a team unranked or no earlier snapshot)\n")

    d = np.array([r[0] for r in rows])
    gap = np.array([r[1] for r in rows], dtype=float)
    rank = np.array([r[2] for r in rows])
    lan = np.array([r[3] is True for r in rows])
    train, test = d < SPLIT, d >= SPLIT
    top = rank <= TOP

    scales = np.arange(200, 2001, 25)
    def fit(mask):
        losses = [log_loss(elo(gap[mask], s)) for s in scales]
        return float(scales[int(np.argmin(losses))])

    s_all, s_top = fit(train), fit(train & top)
    print(f"Coin flip log loss: {np.log(2):.4f}")
    print(f"Fitted scale on training matches: all ranked = {s_all:g}, top-{TOP} = {s_top:g}  (Valve uses 400)\n")

    for label, mask, s_fit in [
        ("Test, all ranked matches", test, s_all),
        (f"Test, both teams top {TOP}", test & top, s_top),
        (f"Test, both top {TOP}, known LAN", test & top & lan, s_top),
    ]:
        print(label)
        print(f"  scale 400      : {summary(elo(gap[mask], 400))}")
        print(f"  scale {s_fit:<8g} : {summary(elo(gap[mask], s_fit))}")
        print()

    print(f"Calibration, test, both top {TOP} (favourite's view):")
    print(f"  {'predicted':>9} {'observed@400':>13} {'observed@fit':>13} {'n':>6}")
    t400 = calibration_table(elo(gap[test & top], 400))
    tfit = calibration_table(elo(gap[test & top], s_top))
    for (p4, o4, n4) in t400:
        print(f"  {p4:9.1%} {o4:13.1%} {'':>13} {n4:6d}")
    print("  --- fitted scale ---")
    for (pf, of, nf) in tfit:
        print(f"  {pf:9.1%} {'':>13} {of:13.1%} {nf:6d}")


if __name__ == "__main__":
    main()
