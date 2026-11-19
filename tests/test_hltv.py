from collections import namedtuple
from datetime import date, timedelta

from pickem.data.hltv import MapResult, group_series, link_series, load_maps, norm_name

D = date(2026, 6, 20)


def mp(map_id, winner, d=D, event="E1", a=("1", "Alpha"), b=("2", "Beta"), name="Mirage"):
    ra, rb = (13, 7) if winner == a[1] else (7, 13)
    return MapResult(map_id, d, a[0], a[1], ra, b[0], b[1], rb, name, event, "Event One")


def test_single_map_is_a_bo1():
    (s,) = group_series([mp(1, "Alpha")])
    assert (s.best_of, s.team_a, s.maps_a, s.maps_b) == (1, "Alpha", 1, 0)


def test_three_maps_form_one_bo3_won_by_the_majority():
    (s,) = group_series([mp(1, "Beta"), mp(2, "Alpha"), mp(3, "Beta")])
    assert (s.best_of, s.team_a, s.maps_a, s.maps_b) == (3, "Beta", 2, 1)


def test_a_drawn_series_is_dropped():
    assert group_series([mp(1, "Alpha"), mp(2, "Beta")]) == []


def test_meetings_days_apart_are_separate_series():
    out = group_series([mp(1, "Alpha"), mp(2, "Beta", d=D + timedelta(days=4))])
    assert [s.best_of for s in out] == [1, 1]


def test_bo5_and_split_of_long_clusters():
    (bo5,) = group_series([mp(i, w) for i, w in enumerate(["Alpha", "Beta", "Alpha", "Alpha"], 1)])
    assert (bo5.best_of, bo5.maps_a, bo5.maps_b) == (5, 3, 1)
    # Four maps split 2-2 can't be one series: two BO3s, each won 2-0.
    out = group_series([mp(i, w) for i, w in enumerate(["Alpha", "Alpha", "Beta", "Beta"], 1)])
    assert [(s.best_of, s.team_a, s.maps_a, s.maps_b) for s in out] == [(3, "Alpha", 2, 0), (3, "Beta", 2, 0)]


V = namedtuple("V", "date winner loser")


def test_norm_name():
    assert norm_name("Team Liquid") == norm_name("Liquid") == "liquid"
    assert norm_name("BC.Game") == "bcgame"
    assert norm_name("Team") == "team"


def test_link_series_learns_short_names_and_needs_the_same_winner():
    nip, liq, faze = ("1", "NIP"), ("2", "Liquid"), ("3", "FaZe")
    valve = [V(D, "Ninjas in Pyjamas", "Team Liquid"),
             V(D + timedelta(days=3), "Ninjas in Pyjamas", "FaZe"),
             V(D + timedelta(days=6), "FaZe", "Ninjas in Pyjamas"),
             V(D + timedelta(days=9), "Team Liquid", "FaZe")]
    series = group_series([
        mp(1, "NIP", a=nip, b=liq),
        mp(2, "NIP", d=D + timedelta(days=3), a=nip, b=faze),
        mp(3, "FaZe", d=D + timedelta(days=7), a=nip, b=faze),     # one day later than Valve's date
        mp(4, "FaZe", d=D + timedelta(days=9), a=liq, b=faze),     # winner disagrees with Valve
    ])
    links = link_series(series, valve)
    assert sorted(links) == [0, 1, 2]
    assert links[2].team_a == "FaZe"


def test_load_skips_draws_and_duplicate_rows(tmp_path):
    p = tmp_path / "maps.csv"
    p.write_text(
        "mapstatsid,date,team1_id,team1,team1_rounds,team2_id,team2,team2_rounds,map,event_id,event\n"
        "10,20/06/26,1,Alpha,13,2,Beta,9,Nuke,5,Ev\n"
        "10,20/06/26,1,Alpha,13,2,Beta,9,Nuke,5,Ev\n"
        "11,20/06/26,1,Alpha,12,2,Beta,12,Inferno,5,Ev\n",
        encoding="utf-8")
    maps = load_maps(p)
    assert [m.map_id for m in maps] == [10]
    assert maps[0].date == date(2026, 6, 20) and maps[0].winner == "Alpha"
