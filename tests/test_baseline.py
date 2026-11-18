import pytest

from pickem.baseline import bo3_from_map, elo_probability, map_from_bo3, matrices_from_points


def test_elo_curve():
    assert elo_probability(1500, 1500) == pytest.approx(0.5)
    assert elo_probability(1900, 1500) == pytest.approx(10 / 11)  # 400 points ~ 91%


@pytest.mark.parametrize("p", [0.1, 0.35, 0.5, 0.62, 0.9])
def test_bo3_inverse_roundtrip(p):
    assert map_from_bo3(bo3_from_map(p)) == pytest.approx(p, abs=1e-9)


def test_bo1_is_closer_to_even_than_bo3():
    p1, p3 = matrices_from_points([1700, 1500])
    assert 0.5 < p1[0, 1] < p3[0, 1]
    assert p1[0, 1] + p1[1, 0] == pytest.approx(1.0)
    assert p3[0, 1] + p3[1, 0] == pytest.approx(1.0)
