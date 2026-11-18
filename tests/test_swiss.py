import random
from collections import Counter

import numpy as np

from pickem import swiss
from pickem.swiss import SwissState, simulate_stage


def coin_flip_matrices():
    p = np.full((16, 16), 0.5)
    return p.tolist(), p.tolist()


def chalk_matrices():
    """The higher initial seed (lower index) always wins."""
    p = [[1.0 if a < b else 0.0 for b in range(16)] for a in range(16)]
    return p, p


def test_round1_matchups_follow_rulebook():
    assert SwissState().next_pairings() == [(i, i + 8) for i in range(8)]


def test_every_stage_has_the_fixed_record_counts():
    # In any 16-team, 3-win/3-loss Swiss: two 3-0, three 3-1, three 3-2,
    # three 2-3, three 1-3, two 0-3.
    p1, p3 = coin_flip_matrices()
    rng = random.Random(1)
    for _ in range(500):
        codes = simulate_stage(p1, p3, rng)
        assert Counter(codes) == {3: 2, 2: 3, 1: 3, -1: 3, -2: 3, -3: 2}


def test_no_rematches_and_bo_format_counts():
    p1, p3 = coin_flip_matrices()
    rng = random.Random(2)
    for _ in range(500):
        log = []
        simulate_stage(p1, p3, rng, log=log)
        assert len(log) == 33
        pairs = [frozenset((a, b)) for _, a, b, _, _ in log]
        assert len(set(pairs)) == 33, "a rematch happened"
        # BO1: rounds 1-2 (16) + the 1-1 pool in round 3 (4) = 20; the rest BO3.
        assert Counter(bo for *_, bo, _ in log) == {1: 20, 3: 13}
        assert all(bo == 1 for rnd, *_, bo, _ in log if rnd <= 2)
        assert all(bo == 3 for rnd, *_, bo, _ in log if rnd >= 4)


def test_chalk_bracket():
    # If the higher seed always wins: round 2 pairs 1v8, 2v7, ..., round 3's
    # 2-0 pool is seeds 1-4 with equal Difficulty Scores, so 1v4 and 2v3:
    # seeds 1 and 2 go 3-0. Mirror image at the bottom: seeds 15, 16 go 0-3.
    p1, p3 = chalk_matrices()
    log = []
    codes = simulate_stage(p1, p3, random.Random(0), log=log)
    assert [codes[0], codes[1]] == [3, 3]
    assert [codes[14], codes[15]] == [-3, -3]
    round2 = [(a, b) for rnd, a, b, _, _ in log if rnd == 2]
    assert round2 == [(0, 7), (1, 6), (2, 5), (3, 4), (8, 15), (9, 14), (10, 13), (11, 12)]


def test_buchholz_matches_rulebook_example():
    # Rulebook: "Team A's prior opponents are 2-0 and 1-1. Team A's
    # Difficulty Score is 2."
    s = SwissState()
    a, opp1, opp2 = 0, 1, 2
    s.opponents[a] = [opp1, opp2]
    s.wins[opp1], s.losses[opp1] = 2, 0
    s.wins[opp2], s.losses[opp2] = 1, 1
    assert s.buchholz(a) == 2


def test_pool_order_uses_buchholz_then_seed():
    s = SwissState()
    # Teams 5 and 9 both 1-0; team 9 faced a stronger opponent.
    for t in (5, 9):
        s.wins[t] = 1
    s.opponents[5] = [12]
    s.opponents[9] = [13]
    s.wins[13] = 1  # 9's opponent has a better record -> higher Difficulty Score
    s.losses[12] = 1
    order = s.pools()[(1, 0)]
    assert order.index(9) < order.index(5)


def test_high_vs_low_backtracks_at_a_dead_end():
    # Pool A, B, C, D (highest to lowest). Greedy gives A-D, then B-C, but
    # B and C already met, so A must take C instead and B plays D.
    A, B, C, D = 0, 1, 2, 3
    met = {frozenset((B, C))}
    pairs = swiss._pair_high_vs_low([A, B, C, D], lambda x, y: frozenset((x, y)) in met)
    assert pairs == [(A, C), (B, D)]


def test_priority_table_skips_rows_with_rematches():
    order = [10, 11, 12, 13, 14, 15]  # positions 1..6
    met = {frozenset((10, 15))}       # 1v6 already played -> rows 1-2 invalid
    pairs = swiss._pair_by_priority_table(order, lambda x, y: frozenset((x, y)) in met)
    assert pairs == [(10, 14), (11, 15), (12, 13)]  # row 3: 1v5, 2v6, 3v4


def test_fixed_results_are_respected():
    p1, p3 = coin_flip_matrices()
    fixed = {(i, i + 8): i + 8 for i in range(8)}  # every round-1 underdog wins
    log = []
    simulate_stage(p1, p3, random.Random(3), fixed=fixed, log=log)
    assert all(w == b for rnd, a, b, _, w in log if rnd == 1)


def test_same_seed_same_result():
    p1, p3 = coin_flip_matrices()
    assert simulate_stage(p1, p3, random.Random(7)) == simulate_stage(p1, p3, random.Random(7))
