from datetime import date

import numpy as np
import pytest

from pickem.evaluate import PointsHistory, accuracy, brier, calibration_table, log_loss


def test_metrics_on_coin_flips():
    p = np.full(10, 0.5)
    assert log_loss(p) == pytest.approx(np.log(2))
    assert brier(p) == pytest.approx(0.25)
    assert accuracy(p) == pytest.approx(0.5)


def test_calibration_counts_every_match():
    p = np.array([0.55, 0.45, 0.9, 0.2, 0.7])
    assert sum(n for *_, n in calibration_table(p, bins=5)) == 5


def test_points_come_from_the_snapshot_before_the_match(tmp_path):
    csv_path = tmp_path / "points.csv"
    csv_path.write_text(
        "snapshot,team,roster,global_rank,region,points\n"
        "2026-10-05,Alpha,a;b;c;d;e,1,Europe,1500\n"
        "2026-11-02,Alpha,a;b;c;d;e,1,Europe,1900\n"
        "2026-11-02,Renamed,f;g;h;i;j,2,Europe,1700\n",
        encoding="utf-8")
    ph = PointsHistory(csv_path)
    # A match on 2026-11-02 must use the 2026-10-05 snapshot, not the same-day one.
    assert ph.lookup(date(2026, 11, 2), "Alpha", None) == (1500.0, 1)
    assert ph.lookup(date(2026, 11, 3), "Alpha", None) == (1900.0, 1)
    # Found by lineup (3+ shared players) even under a different name.
    assert ph.lookup(date(2026, 11, 3), "Old name", ("f", "g", "h", "x", "y")) == (1700.0, 2)
    # Unranked -> None.
    assert ph.lookup(date(2026, 11, 3), "Nobody", ("p", "q", "r", "s", "t")) is None
    assert ph.lookup(date(2026, 10, 1), "Alpha", None) is None  # no earlier snapshot
