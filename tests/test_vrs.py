from datetime import date

from pickem.data.vrs import Match, build_history, matches_in_snapshot, parse_page

PAGE = """### Roster Details<br />
Team Name: Alpha<br />
Roster: zed, Amy, bob, Cat, dan<br />
Global Rank: [7](../../standings_global_2026_11_02.md)<br />
<br />
Region: [Europe]( ../../standings_europe_2026_11_02.md)<br />
Final Rank Value:  1712.5<br />

| Match Played | Match ID | Date       | Opponent | W/L | Age Weight | Event Weight | Bounty Collected | Opponent Network | LAN Wins  | H2H Adj. | Roster |
| -: | -: | :- | :- | :- | :- | :- | :- | :- | :- | -: | :- |
|            3 |       10 | 2026-10-30 | Beta     | W   | 1.000      | 0.800        | -                | 0.4 (0.4)        | 1 (1.000) |     5.00 | zed, Amy, bob, Cat, dan |
|            2 |       20 | 2026-10-20 | Gamma    | W   | 1.000      | -            | -                | -                | 0 (0.000) |     4.00 | zed, Amy, bob, Cat, eve |
|            1 |       30 | 2026-10-10 | Beta     | L   | 1.000      | -            | -                | -                | -         |    -6.00 | zed, Amy, bob, Cat, eve |
"""

BETA_PAGE = """Team Name: Beta<br />
Roster: p1, p2, p3, p4, p5<br />
| Match Played | Match ID | Date | Opponent | W/L | Age Weight | Event Weight | Bounty Collected | Opponent Network | LAN Wins | H2H Adj. | Roster |
| 1 | 10 | 2026-10-30 | Alpha | L | 1.000 | - | - | - | - | -5.00 | p1, p2, p3, p4, p5 |
"""


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_page_header_and_rows(tmp_path):
    page = parse_page(write(tmp_path, "a.md", PAGE), date(2026, 11, 2))
    assert (page.team, page.global_rank, page.region, page.points) == ("Alpha", 7, "Europe", 1712.5)
    assert page.roster == ("Amy", "bob", "Cat", "dan", "zed")  # sorted, case-insensitive
    r10, r20, r30 = page.rows
    assert (r10.won, r10.event_weight, r10.lan) == (True, 0.8, True)
    assert (r20.event_weight, r20.lan) == (None, False)  # LAN column "0" = online
    assert (r30.won, r30.lan) == (False, None)           # "-" = not shown
    assert "eve" in r20.roster  # lineup at match time, not today's roster


def test_two_sides_merge_into_one_match(tmp_path):
    snap = date(2026, 11, 2)
    pages = [parse_page(write(tmp_path, "a.md", PAGE), snap), parse_page(write(tmp_path, "b.md", BETA_PAGE), snap)]
    ms = {(m.date, m.winner, m.loser): m for m in matches_in_snapshot(pages)}
    m = ms[(date(2026, 10, 30), "Alpha", "Beta")]
    assert m.loser_roster == ("p1", "p2", "p3", "p4", "p5")
    assert m.lan is True
    # Gamma has no page: one-sided match, loser lineup unknown.
    assert ms[(date(2026, 10, 20), "Alpha", "Gamma")].loser_roster is None
    assert len(ms) == 3


def M(d, w, l, snap, lan=None, wr=("a", "b", "c", "d", "e"), lr=("f", "g", "h", "i", "j")):
    return Match(d, w, l, wr, lr, lan, None, snap)


def test_history_survives_renames_and_fills_flags():
    s1, s2 = date(2024, 8, 6), date(2024, 8, 14)
    d1, d2 = date(2024, 8, 1), date(2024, 8, 10)
    snap1 = [M(d1, "A", "PERA", s1)]
    # In the later snapshot the old match is relabelled and now shows a LAN flag.
    snap2 = [M(d1, "A", "ex-PERA", s2, lan=True), M(d2, "A", "B", s2)]
    hist = build_history([(s1, snap1), (s2, snap2)])
    assert [(m.date, m.loser) for m in hist] == [(d1, "PERA"), (d2, "B")]
    assert hist[0].lan is True  # filled in via the matching lineups


def test_late_entries_are_kept_once():
    s1, s2 = date(2024, 8, 6), date(2024, 8, 14)
    late = date(2024, 8, 5)  # played before snapshot 1 but missing from it
    hist = build_history([(s1, []), (s2, [M(late, "A", "B", s2)])])
    assert [(m.date, m.winner) for m in hist] == [(late, "A")]
    # If snapshot 1 already had it, snapshot 2 must not add it again.
    hist = build_history([(s1, [M(late, "A", "B", s1)]), (s2, [M(late, "A", "B", s2)])])
    assert len(hist) == 1


def test_genuine_same_day_rematches_are_kept():
    s1 = date(2024, 8, 6)
    d = date(2024, 8, 1)
    hist = build_history([(s1, [M(d, "A", "B", s1), M(d, "B", "A", s1)])])
    assert len(hist) == 2
