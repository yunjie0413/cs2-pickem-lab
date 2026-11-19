"""Strength uncertainty for the simulator (Step 7).

A team's true strength at an event differs from our estimate, and the
difference holds for the whole event: an underrated team tends to win
several matches, not one. Simulating every match with fixed probabilities
treats those errors as independent and makes extreme records (3-0, 0-3) too
rare when a team is mis-rated.

So each simulated stage draws one offset per team, e_i ~ N(0, sigma^2), in
the units of the blend logit (our rating gap + VRS gap, before the format
scale), and plays the whole stage with

    BO3: q_ij = sigmoid(s * (kappa * logit_ij + e_i - e_j))      s = BO3 scale
    BO1: from q_ij, assuming independent maps (as without uncertainty)

kappa = sqrt(1 + pi s^2 sigma^2 / 4) undoes the flattening that averaging
over the offsets causes (E[sigmoid(x + N(0, t^2))] ~ sigmoid(x / sqrt(1 + pi
t^2 / 8)), here t^2 = 2 s^2 sigma^2), so a single match's probability,
averaged over the draws, stays what the model was calibrated to; only the
links between matches change. sigma is measured on past LAN events by
scripts/fit_uncertainty.py.
"""
from __future__ import annotations

import math

import numpy as np

from .baseline import bo3_from_map

_P = np.linspace(0.0, 1.0, 20001)
_Q = np.array([bo3_from_map(p) for p in _P])   # increasing in p


def map_from_bo3_array(q: np.ndarray) -> np.ndarray:
    """Vectorised inverse of bo3_from_map (to about 1e-5)."""
    return np.interp(q, _Q, _P)


def kappa(sigma: float, bo3_scale: float) -> float:
    return math.sqrt(1.0 + math.pi * bo3_scale ** 2 * sigma ** 2 / 4.0)


def matrices(logit: np.ndarray, bo3_scale: float, sigma: float, e: np.ndarray | None = None):
    """(p_bo1, p_bo3) for one draw of offsets `e` (None = no offsets)."""
    x = kappa(sigma, bo3_scale) * logit
    if e is not None:
        x = x + e[:, None] - e[None, :]
    q = 1.0 / (1.0 + np.exp(-bo3_scale * x))
    p1 = map_from_bo3_array(q)
    np.fill_diagonal(q, 0.5)
    np.fill_diagonal(p1, 0.5)
    return p1, q


def make_sampler(logit: np.ndarray, bo3_scale: float, sigma: float):
    """Sampler for simulate.run: one set of team offsets per simulated stage."""
    n = logit.shape[0]

    def sampler(rng: np.random.Generator):
        return matrices(logit, bo3_scale, sigma, rng.normal(0.0, sigma, n))

    return sampler


def marginal_check(logit: np.ndarray, bo3_scale: float, sigma: float, draws: int = 4000, seed: int = 0):
    """Largest gap between the averaged per-draw probabilities and the fixed ones (BO1, BO3)."""
    rng = np.random.default_rng(seed)
    fixed1, fixed3 = matrices(logit, bo3_scale, 0.0)
    s1, s3 = np.zeros_like(logit), np.zeros_like(logit)
    for _ in range(draws):
        a, b = matrices(logit, bo3_scale, sigma, rng.normal(0.0, sigma, logit.shape[0]))
        s1 += a
        s3 += b
    return float(np.abs(s1 / draws - fixed1).max()), float(np.abs(s3 / draws - fixed3).max())
