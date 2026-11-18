"""Baseline 0: turn Valve's VRS points into match probabilities.

This is a placeholder and a benchmark, not the real model. Any model we build
later has to beat it on past matches to be worth using.

Assumptions (each is something to test, not a fact):
  1. VRS points follow the Elo curve Valve's own code uses
     (ValveSoftware/counter-strike_regional_standings, model/glicko.js):
     P(A beats B) = 1 / (1 + 10^((R_B - R_A) / 400)).
  2. That number is read as a *series* (BO3) probability, because most
     tier-1 matches feeding VRS are BO3.
  3. Maps are independent with the same win chance p, so a BO3 is won with
     probability p^2 (3 - 2p). We invert that to get p, and use p for BO1.
     Effect: BO1s are closer to 50/50 than BO3s, as they should be.
  4. Valve's own 2023 evaluation found VRS overconfident (observed win rates
     less extreme than predicted). ``scale`` > 400 shrinks every probability
     toward 50%; fitting it on past matches is a later step.
"""
from __future__ import annotations

import numpy as np


def elo_probability(r_a: float, r_b: float, scale: float = 400.0) -> float:
    return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / scale))


def bo3_from_map(p: float) -> float:
    """P(win a BO3) when each map is won independently with probability p."""
    return p * p * (3.0 - 2.0 * p)


def map_from_bo3(q: float, tol: float = 1e-12) -> float:
    """Inverse of bo3_from_map (monotone on [0, 1]), by bisection."""
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if bo3_from_map(mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def matrices_from_points(points: list[float], scale: float = 400.0) -> tuple[np.ndarray, np.ndarray]:
    """(p_bo1, p_bo3) matrices: entry [a, b] = P(team a beats team b)."""
    n = len(points)
    p_bo1 = np.full((n, n), 0.5)
    p_bo3 = np.full((n, n), 0.5)
    for a in range(n):
        for b in range(n):
            if a != b:
                q = elo_probability(points[a], points[b], scale)
                p_bo3[a, b] = q
                p_bo1[a, b] = map_from_bo3(q)
    return p_bo1, p_bo3
