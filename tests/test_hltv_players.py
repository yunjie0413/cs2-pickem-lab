from datetime import date

import pytest

from pickem.data.hltv_players import K_ROUNDS, PlayerRatings, _num


def row(month, pid, nick, team, rounds, rating, f="All"):
    y, m = month
    return {"start": f"{y}-{m:02d}-01", "end": f"{y}-{m:02d}-28", "filter": f, "player_id": pid, "nick": nick,
            "teams": team, "maps": "1", "rounds": str(rounds), "net_kills_24": "0", "eco_swing": "0%",
            "rnd_swing": "0%", "rating": str(rating)}


def test_number_parsing_handles_unicode_minus_and_percent():
    assert _num("−5.44") == -5.44
    assert _num("+20.31%") == 20.31


def test_only_the_six_months_before_the_match_month_count():
    rows = [row((2024, 12), "1", "a", "T", 1000, 1.50),   # window for July is January-June: outside
            row((2025, 3), "1", "a", "T", 1000, 1.10),
            row((2025, 7), "1", "a", "T", 1000, 0.50)]    # the match month itself: outside
    pr = PlayerRatings(rows)
    n5, r5, nr, rr = pr.window("1", date(2025, 7, 20))
    assert (n5, nr, rr) == (0, 1000, pytest.approx(1.10))


def test_rest_rounds_are_all_minus_top50():
    rows = [row((2025, 3), "1", "a", "T", 1000, 1.10), row((2025, 3), "1", "a", "T", 400, 0.95, "Top50")]
    n5, r5, nr, rr = PlayerRatings(rows).window("1", date(2025, 5, 1))
    assert (n5, r5, nr) == (400, pytest.approx(0.95), 600)
    assert rr == pytest.approx((1.10 * 1000 - 0.95 * 400) / 600)


def test_too_little_data_means_no_translation_and_unknown_players_get_the_prior():
    rows = [row((2025, 5), "1", "star", "T", 3000, 1.30), row((2025, 5), "1", "star", "T", 3000, 1.20, "Top50")]
    pr = PlayerRatings(rows)
    assert (pr.delta, pr.w, pr.mu0) == (0.0, 1.0, 1.0)
    assert pr.value("nobody", None, date(2025, 6, 10)) == pytest.approx(1.0)
    expected = (1.0 * K_ROUNDS + 1.20 * 3000) / (K_ROUNDS + 3000)   # all his rounds were top-50 rounds
    assert pr.value("STAR", None, date(2025, 6, 10)) == pytest.approx(expected)


def test_rest_rounds_count_less_and_after_the_inflation_gap():
    pr = PlayerRatings([row((2025, 4), "1", "sub", "T", 800, 1.25)])   # only weak opponents
    pr.delta, pr.w, pr.mu0 = 0.09, 0.2, 0.95
    expected = (0.95 * K_ROUNDS + 0.2 * 800 * (1.25 - 0.09)) / (K_ROUNDS + 0.2 * 800)
    assert pr.value("sub", None, date(2025, 6, 1)) == pytest.approx(expected)
    assert 0.95 < pr.value("sub", None, date(2025, 6, 1)) < 1.25 - 0.09   # between the prior and his deflated rating


def test_inflation_gap_is_fitted_from_players_with_both_kinds_of_rounds():
    rows = []
    for i in range(60):
        r5 = 0.9 + 0.003 * i
        for k in range(12):                       # 2024-06 .. 2025-05, all before the end of training
            month = (2024 + (5 + k) // 12, (5 + k) % 12 + 1)
            rows.append(row(month, str(i), f"p{i}", "T", 600, r5 + 0.05))         # half the rounds at r5 + 0.10
            rows.append(row(month, str(i), f"p{i}", "T", 300, r5, "Top50"))
    pr = PlayerRatings(rows)
    assert pr.delta == pytest.approx(0.10)
    assert pr.gap_n >= 50


def test_shared_nickname_resolved_by_team_then_rounds():
    rows = [row((2025, 4), "1", "max", "9z", 200, 0.80), row((2025, 4), "2", "max", "Other", 900, 1.20)]
    pr = PlayerRatings(rows)
    assert pr.resolve("max", "9z", date(2025, 5, 3)) == "1"
    assert pr.resolve("max", "Nobody", date(2025, 5, 3)) == "2"
