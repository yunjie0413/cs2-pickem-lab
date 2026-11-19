import math
from datetime import date, timedelta

import numpy as np
import pytest

from pickem.model_v1 import MEAN, Engine, MatchIn, Params, fit_logistic

L1 = ("a1", "a2", "a3", "a4", "a5")
L2 = ("b1", "b2", "b3", "b4", "b5")
D0 = date(2025, 1, 1)


def match(winner, loser, d=D0, wl=L1, ll=L2, lan=None):
    return MatchIn(d, winner, loser, wl, ll, lan)


def test_first_meeting_of_new_teams_is_a_coin_flip_and_winner_gains():
    eng = Engine(Params())
    pred = eng.process(match("A", "B"))
    assert pred.z == 0.0  # prediction made before the update
    a, b = eng.teams[pred.team_a], eng.teams[pred.team_b]
    assert a.rating > MEAN > b.rating


def test_rename_with_same_lineup_keeps_the_team():
    eng = Engine(Params())
    first = eng.process(match("PERA", "B"))
    later = eng.process(match("ex-PERA", "B", d=D0 + timedelta(days=1)))
    assert later.team_a == first.team_a


def test_renamed_team_is_still_found_by_its_new_name_after_a_big_roster_change():
    regions = {"PERA": "Asia", "ex-PERA": "Europe"}
    eng = Engine(Params(), regions)
    first = eng.process(match("PERA", "B"))
    eng.process(match("ex-PERA", "B", d=D0 + timedelta(days=1)))   # renamed, same lineup
    team = eng.teams[first.team_a]
    assert team.name == "ex-PERA" and eng.region_of(team) == "Europe"
    three_new = ("a1", "a2", "n1", "n2", "n3")                     # only 2 shared: found by name
    later = eng.process(match("ex-PERA", "B", d=D0 + timedelta(days=2), wl=three_new))
    assert later.team_a == first.team_a


def test_former_players_cannot_claim_a_team_that_has_replaced_them():
    eng = Engine(Params())
    old = ("a1", "a2", "a3", "a4", "a5")
    first = eng.process(match("Permitta", "B", wl=old))
    eng.process(match("Permitta", "B", d=D0 + timedelta(days=1), wl=("a1", "a2", "a3", "b1", "b2")))
    eng.process(match("Permitta", "B", d=D0 + timedelta(days=2), wl=("b1", "b2", "c1", "c2", "c3")))
    # a1-a3 last played for Permitta, but Permitta's lineup no longer has them.
    walczaki = eng.process(match("Walczaki", "B", d=D0 + timedelta(days=3), wl=("a1", "a2", "a3", "e1", "e2")))
    assert walczaki.team_a != first.team_a
    again = eng.process(match("Permitta", "B", d=D0 + timedelta(days=4), wl=("b1", "b2", "c1", "c2", "c3")))
    assert again.team_a == first.team_a


def test_a_name_only_continues_the_team_that_still_uses_it():
    eng = Engine(Params())
    first = eng.process(match("Old", "B", wl=L1))
    eng.process(match("New", "B", d=D0 + timedelta(days=1), wl=L1))       # renamed
    fresh = eng.process(match("Old", "B", d=D0 + timedelta(days=2), wl=("z1", "z2", "z3", "z4", "z5")))
    assert fresh.team_a != first.team_a                                   # "Old" now names nobody


def test_roster_reset_scales_with_players_changed():
    p = Params(roster_reset=0.5, decay_days=math.inf)
    eng = Engine(p)
    for i in range(5):  # make team A clearly above average
        eng.process(match("A", f"X{i}", wl=L1, ll=(f"x{i}1", f"x{i}2", f"x{i}3", f"x{i}4", f"x{i}5")))
    tid = eng.by_name["A"]
    before, mu = eng.teams[tid].rating, eng.mean()
    # Same name, 3 new players (only 2 shared -> found by name, 3 changed).
    new_lineup = ("a1", "a2", "n1", "n2", "n3")
    eng._prepare(tid, 3, D0)
    expected = mu + (before - mu) * (1 - 0.5 * 3 / 5)
    assert eng.teams[tid].rating == pytest.approx(expected)
    _, changed = eng.resolve("A", frozenset(new_lineup))
    assert changed == 3


def test_time_decay_pulls_toward_the_current_average():
    eng = Engine(Params(k_new=4.0, decay_days=100))
    for i in range(6):
        eng.process(match("A", f"X{i}", d=D0 + timedelta(days=i),
                          ll=(f"x{i}1", f"x{i}2", f"x{i}3", f"x{i}4", f"x{i}5")))
    tid = eng.by_name["A"]
    r, mu = eng.teams[tid].rating, eng.mean()
    assert mu == pytest.approx(sum(t.rating for t in eng.teams) / len(eng.teams))
    eng._prepare(tid, 0, D0 + timedelta(days=105))  # last match on day 5 -> 100 days idle
    assert eng.teams[tid].rating == pytest.approx(mu + (r - mu) * math.exp(-1))


def test_inactivity_can_bring_back_the_new_team_boost():
    eng = Engine(Params(decay_days=math.inf, forget_days=50))
    eng.process(match("A", "B"))
    tid = eng.by_name["A"]
    eng._prepare(tid, 0, D0 + timedelta(days=50))
    assert eng.teams[tid].n == pytest.approx(math.exp(-1))


def test_region_offsets_only_move_on_cross_region_matches():
    regions = {"A": "Europe", "B": "Asia", "C": "Europe"}
    eng = Engine(Params(k_region=4.0), regions)
    eng.process(match("A", "C", ll=("c1", "c2", "c3", "c4", "c5")))  # same region: no change
    assert eng.region_offset["Europe"] == 0
    eng.process(match("A", "B", d=D0 + timedelta(days=1)))
    assert eng.region_offset["Europe"] > 0 > eng.region_offset["Asia"]


def test_volatility_rises_when_the_favourite_loses():
    eng = Engine(Params(vol_rate=0.05))
    a = eng.resolve("Fav", frozenset(L1))[0]
    b = eng.resolve("Dog", frozenset(L2))[0]
    eng.teams[a].rating, eng.teams[b].rating = 1800.0, 1400.0
    eng.process(match("Dog", "Fav", wl=L2, ll=L1))
    assert eng.teams[a].vol > 0 and eng.teams[b].vol > 0


def test_lan_weight_scales_the_update():
    plain, lan = Engine(Params(w_lan=2.0)), Engine(Params(w_lan=2.0))
    plain.process(match("A", "B"))
    lan.process(match("A", "B", lan=True))
    gain = lambda e: e.teams[e.by_name["A"]].rating - MEAN
    assert gain(lan) == pytest.approx(2 * gain(plain))


def test_roster_change_brings_back_part_of_the_new_team_boost():
    eng = Engine(Params(roster_new=0.5, decay_days=math.inf))
    for i in range(20):
        eng.process(match("A", f"X{i}", d=D0 + timedelta(days=i),
                          ll=(f"x{i}1", f"x{i}2", f"x{i}3", f"x{i}4", f"x{i}5")))
    tid = eng.by_name["A"]
    assert eng.teams[tid].n == 20
    eng._prepare(tid, 2, D0 + timedelta(days=30))   # 2 of 5 players changed
    assert eng.teams[tid].n == pytest.approx(20 * (1 - 0.5 * 2 / 5))


class FakePlayers:
    def __init__(self, values):
        self.values = values

    def value(self, nick, team, on):
        return self.values.get(nick, 1.0)


def test_player_ratings_move_the_rating_on_a_lineup_change_and_back_for_a_stand_in():
    players = FakePlayers({"a5": 1.00, "s1": 0.80})
    eng = Engine(Params(roster_skill=300.0, decay_days=math.inf), players=players)
    eng.process(match("A", "B"))
    tid = eng.by_name["A"]
    before = eng.teams[tid].rating
    stand_in = ("a1", "a2", "a3", "a4", "s1")
    assert eng.skill_change(tid, frozenset(stand_in), "A", D0) == pytest.approx(-0.20)
    eng.process(match("A", "C", d=D0 + timedelta(days=1), wl=stand_in, ll=("c1", "c2", "c3", "c4", "c5")))
    # the -60 point adjustment came before this match's update: check it through the prediction
    t = eng.teams[tid]
    assert eng.skill_change(tid, frozenset(L1), "A", D0) == pytest.approx(+0.20)  # a5 returns: reversed
    off = Engine(Params(decay_days=math.inf), players=players)
    off.process(match("A", "B"))
    assert off.skill_change(off.by_name["A"], frozenset(stand_in), "A", D0) == 0.0  # factor off
    assert t.rating != before


def test_player_rating_adjustment_size():
    players = FakePlayers({"a5": 1.00, "n1": 1.25})
    eng = Engine(Params(roster_skill=400.0, decay_days=math.inf, k=0.0001), players=players)
    eng.process(match("A", "B"))
    tid = eng.by_name["A"]
    before = eng.teams[tid].rating
    eng.process(match("B", "A", d=D0 + timedelta(days=1), wl=L2, ll=("a1", "a2", "a3", "a4", "n1")))
    # with a tiny update size, the change is almost all from the lineup change: 400 x 0.25 = 100
    assert eng.teams[tid].rating - before == pytest.approx(100.0, abs=0.5)


def test_new_teams_start_at_the_current_average():
    eng = Engine(Params(k_new=8.0, decay_days=200, roster_reset=0.3))
    for i in range(30):  # uneven update sizes: the average drifts away from MEAN
        eng.process(match(f"T{i % 7}", f"U{i}", d=D0 + timedelta(days=5 * i), wl=None, ll=None))
    avg = sum(t.rating for t in eng.teams) / len(eng.teams)
    assert eng.mean() == pytest.approx(avg) and abs(avg - MEAN) > 1
    tid, _ = eng.resolve("Newcomer", None)
    assert eng.teams[tid].rating == pytest.approx(avg)


def test_fit_logistic_recovers_a_known_scale():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1.5, 20000)
    won = rng.random(20000) < 1 / (1 + np.exp(-0.7 * x))
    rows = np.where(won, x, -x)  # write every row from the winner's side
    w = fit_logistic(rows[:, None])
    assert w[0] == pytest.approx(0.7, abs=0.05)
