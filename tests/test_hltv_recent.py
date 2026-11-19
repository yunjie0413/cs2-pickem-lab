from datetime import date

from pickem.data.hltv_recent import recent_inputs

TEAMS = [
    {"name": "PVISION", "org_name": "PARIVISION", "roster": ["a1", "a2", "a3", "a4", "a5"]},
    {"name": "Liquid", "roster": ["b1", "b2", "b3", "b4", "b5"]},
    {"name": "M80", "roster": ["c1", "c2", "c3", "c4", "c5"]},
]
VALVE = {"PARIVISION", "Liquid", "M80", "BetBoom", "NAVI"}


def row(team, utc, t1, t2, score, mid, fmt="bo3", event="E"):
    return {"event_team": team, "utc": utc, "team1": t1, "team2": t2, "score": score, "fmt": fmt,
            "event": event, "match_id": mid}


def test_shared_match_counted_once_with_event_lineups():
    rows = [row("Liquid", "2026-11-03T04:00:00.000Z", "Liquid", "PARIVISION", "0-2", "1"),
            row("PVISION", "2026-11-03T04:00:00.000Z", "PARIVISION", "Liquid", "2-0", "1"),
            row("PVISION", "2026-11-06T04:00:00.000Z", "Natus Vincere", "PARIVISION", "2-1", "2")]
    rec = recent_inputs(rows, TEAMS, {"Natus Vincere": "NAVI"}, VALVE, after=date(2026, 11, 1))
    assert len(rec.inputs) == 2 and not rec.skipped
    m = rec.inputs[0]
    assert (m.winner, m.loser) == ("PARIVISION", "Liquid")
    assert list(m.winner_lineup) == TEAMS[0]["roster"] and list(m.loser_lineup) == TEAMS[1]["roster"]
    n = rec.inputs[1]
    assert (n.winner, n.loser, n.winner_lineup) == ("NAVI", "PARIVISION", None)


def test_normalised_names_unknown_teams_and_old_dates():
    rows = [row("Liquid", "2026-11-04T09:00:00.000Z", "Liquid", "BETBOOM", "1-2", "3"),
            row("Liquid", "2026-11-05T09:00:00.000Z", "Liquid", "Nobody Esports", "2-0", "4"),
            row("Liquid", "2026-11-01T09:00:00.000Z", "Liquid", "BETBOOM", "2-0", "5")]
    rec = recent_inputs(rows, TEAMS, {}, VALVE, after=date(2026, 11, 1))
    assert [(m.winner, m.loser) for m in rec.inputs] == [("BetBoom", "Liquid")]
    assert len(rec.skipped) == 1 and "Nobody Esports" in rec.skipped[0]


def test_single_row_page_finds_its_own_side():
    rows = [row("M80", "2026-11-10T20:00:00.000Z", "BETBOOM", "M80", "13-7", "6", fmt="nuke")]
    rec = recent_inputs(rows, TEAMS, {}, VALVE, after=date(2026, 11, 1))
    m = rec.inputs[0]
    assert (m.winner, m.loser, m.winner_lineup) == ("BetBoom", "M80", None)
    assert list(m.loser_lineup) == TEAMS[2]["roster"]
