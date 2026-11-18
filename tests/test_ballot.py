import numpy as np
import pytest

from pickem import simulate
from pickem.ballot import Ballot, BallotRules, Grader, best_expected, best_threshold, confirm
from pickem.baseline import matrices_from_points

BALLOT = Ballot(perfect=(0, 1), advance=(2, 3, 4, 5, 6, 7), winless=(14, 15))


def codes_row(**records):
    """Build one simulated outcome: default every team 2-3 (code -1)."""
    row = np.full(16, -1, dtype=np.int8)
    for idx, code in records.items():
        row[int(idx[1:])] = code
    return row


def test_grading_counts_exact_records():
    # t0 3-0 (hit), t1 3-1 (3-0 pick misses), t2 3-0 (advance pick misses:
    # advance means 3-1 or 3-2), t3 3-2 (hit), t15 0-3 (hit).
    row = codes_row(t0=3, t1=2, t2=3, t3=1, t15=-3)
    g = Grader(row[None, :])
    assert g.hits(BALLOT)[0] == 3


def test_advance_includes_perfect_option():
    row = codes_row(t0=3, t1=2, t2=3, t3=1, t15=-3)
    g = Grader(row[None, :], BallotRules(advance_includes_perfect=True))
    assert g.hits(BALLOT)[0] == 4


def test_ballot_validation():
    with pytest.raises(ValueError):
        Ballot((0, 1), (1, 2, 3, 4, 5, 6), (14, 15)).check(BallotRules())


@pytest.fixture(scope="module")
def sims():
    points = list(np.linspace(1600, 1250, 16))
    p1, p3 = matrices_from_points(points)
    teams = [f"T{i + 1}" for i in range(16)]
    return simulate.run(teams, p1, p3, n_sims=4000, seed=11)


def test_threshold_search_agrees_with_direct_grading(sims):
    g = Grader(sims.codes)
    top = best_threshold(g, top=5)
    for ballot, p in top:
        ballot.check(g.rules)
        assert p == pytest.approx(g.p_success(ballot))
    assert [p for _, p in top] == sorted((p for _, p in top), reverse=True)


def test_best_expected_beats_threshold_choice_on_expectation(sims):
    # Each optimiser should win on its own objective (same simulations).
    g = Grader(sims.codes)
    be = best_expected(g)
    bt, _ = best_threshold(g, top=1)[0]
    assert g.expected(be) >= g.expected(bt) - 1e-12
    assert g.p_success(bt) >= g.p_success(be) - 1e-12


def test_confirm_sorts_by_fresh_probability(sims):
    g = Grader(sims.codes)
    cands = [b for b, _ in best_threshold(g, top=3)]
    out = confirm(cands, g)
    assert [p for _, p in out] == sorted((p for _, p in out), reverse=True)
