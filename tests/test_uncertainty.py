import numpy as np
import pytest

from pickem.baseline import bo3_from_map, map_from_bo3
from pickem.uncertainty import make_sampler, map_from_bo3_array, marginal_check, matrices


def logits(n=6, seed=1):
    r = np.random.default_rng(seed).normal(0, 0.6, n)
    return r[:, None] - r[None, :]


def test_vectorised_bo1_conversion_matches_the_exact_one():
    q = np.array([0.1, 0.35, 0.5, 0.8, 0.97])
    assert map_from_bo3_array(q) == pytest.approx([map_from_bo3(x) for x in q], abs=1e-4)
    assert bo3_from_map(float(map_from_bo3_array(np.array([0.7]))[0])) == pytest.approx(0.7, abs=1e-4)


def test_no_spread_gives_the_fixed_matrices():
    L = logits()
    p1, p3 = matrices(L, 1.1, 0.0)
    assert p3[0, 1] == pytest.approx(1 / (1 + np.exp(-1.1 * L[0, 1])))
    assert np.allclose(p3 + p3.T, 1.0) and np.allclose(np.diag(p1), 0.5)


def test_averaged_over_draws_a_single_match_keeps_its_probability():
    d1, d3 = marginal_check(logits(), 1.1, 0.35, draws=6000)
    assert d3 < 0.01 and d1 < 0.01


def test_without_the_correction_the_average_would_be_flatter():
    L = logits()
    rng = np.random.default_rng(3)
    fixed = matrices(L, 1.1, 0.0)[1]
    raw = np.mean([1 / (1 + np.exp(-1.1 * (L + e[:, None] - e[None, :])))
                   for e in rng.normal(0, 0.35, (6000, L.shape[0]))], axis=0)
    i, j = np.unravel_index(np.argmax(np.abs(fixed - 0.5)), fixed.shape)
    assert abs(raw[i, j] - 0.5) < abs(fixed[i, j] - 0.5) - 0.005


def test_sampler_draws_one_offset_per_team_per_stage():
    s = make_sampler(logits(), 1.1, 0.3)
    a1, a3 = s(np.random.default_rng(5))
    b1, b3 = s(np.random.default_rng(5))
    c1, c3 = s(np.random.default_rng(6))
    assert np.array_equal(a3, b3) and not np.array_equal(a3, c3)
    assert np.allclose(a3 + a3.T, 1.0)
