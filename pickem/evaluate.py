"""Tools for testing match models on past matches.

Main metric: log loss = average of -ln(probability the model gave to what
actually happened). Lower is better. A coin flip scores ln 2 = 0.693.
Log loss punishes confident mistakes hard, which is what we want: the
simulator relies on the probabilities themselves, not just on picking the
favourite. Brier score (mean squared error of the probability) and accuracy
are reported alongside.
"""
from __future__ import annotations

import bisect
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from .data.vrs import Roster


def log_loss(p_actual: np.ndarray) -> float:
    """p_actual: probability the model gave to the actual winner, per match."""
    p = np.clip(p_actual, 1e-9, 1 - 1e-9)
    return float(-np.log(p).mean())


def brier(p_actual: np.ndarray) -> float:
    return float(((1 - p_actual) ** 2).mean())


def accuracy(p_actual: np.ndarray) -> float:
    return float((p_actual > 0.5).mean() + 0.5 * (p_actual == 0.5).mean())


def calibration_table(p_actual: np.ndarray, bins: int = 10) -> list[tuple[float, float, int]]:
    """(mean predicted, observed win rate, count) for the favourite, by bins.

    Each match is viewed from the favourite's side, so predictions are in
    [0.5, 1]. A well-calibrated model has observed ≈ predicted in every bin.
    """
    fav_p = np.maximum(p_actual, 1 - p_actual)
    fav_won = (p_actual >= 0.5).astype(float)
    edges = np.linspace(0.5, 1.0, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (fav_p >= lo) & (fav_p < hi) if hi < 1 else (fav_p >= lo)
        if mask.sum():
            out.append((float(fav_p[mask].mean()), float(fav_won[mask].mean()), int(mask.sum())))
    return out


def summary(p_actual: np.ndarray) -> str:
    return (f"n={len(p_actual):,}  log loss {log_loss(p_actual):.4f}  "
            f"Brier {brier(p_actual):.4f}  accuracy {accuracy(p_actual):.1%}")


# --- loading -----------------------------------------------------------------

@dataclass(frozen=True)
class MatchRecord:
    date: date
    winner: str
    loser: str
    winner_roster: Roster | None
    loser_roster: Roster | None
    lan: bool | None
    event_weight: float | None


def _roster(text: str) -> Roster | None:
    return tuple(text.split(";")) if text else None


def load_matches(path: Path) -> list[MatchRecord]:
    out = []
    with open(path, newline="", encoding="utf-8") as fp:
        for r in csv.DictReader(fp):
            out.append(MatchRecord(
                date=date.fromisoformat(r["date"]),
                winner=r["winner"], loser=r["loser"],
                winner_roster=_roster(r["winner_roster"]), loser_roster=_roster(r["loser_roster"]),
                lan=None if r["lan"] == "" else r["lan"] == "1",
                event_weight=None if r["event_weight"] == "" else float(r["event_weight"]),
            ))
    return out


class PointsHistory:
    """VRS points of every ranked roster at every snapshot.

    lookup() returns a team's points from the latest snapshot strictly
    *before* a date, so a test never uses information from after the match.
    A team is found by lineup (3+ shared players) when the lineup is known,
    otherwise by name. Lineup first, because names change.
    """

    def __init__(self, path: Path):
        self.by_snap: dict[date, list[tuple[str, frozenset, float, int]]] = defaultdict(list)
        with open(path, newline="", encoding="utf-8") as fp:
            for r in csv.DictReader(fp):
                if r["points"]:
                    self.by_snap[date.fromisoformat(r["snapshot"])].append((
                        r["team"], frozenset(p.lower() for p in r["roster"].split(";")),
                        float(r["points"]), int(r["global_rank"] or 10**6)))
        self.snaps = sorted(self.by_snap)
        # player -> indices of the rosters containing them, per snapshot (fast lineup lookup)
        self.player_index: dict[date, dict[str, list[int]]] = {}
        for snap, entries in self.by_snap.items():
            idx: dict[str, list[int]] = defaultdict(list)
            for i, e in enumerate(entries):
                for player in e[1]:
                    idx[player].append(i)
            self.player_index[snap] = idx

    def snapshot_before(self, d: date) -> date | None:
        i = bisect.bisect_left(self.snaps, d) - 1
        return self.snaps[i] if i >= 0 else None

    def lookup(self, d: date, team: str, roster: Roster | None) -> tuple[float, int] | None:
        """(points, global rank) or None if the team wasn't ranked."""
        snap = self.snapshot_before(d)
        if snap is None:
            return None
        entries = self.by_snap[snap]
        if roster:
            shared = Counter(i for p in roster for i in self.player_index[snap].get(p.lower(), ()))
            if shared:
                i, n = max(shared.items(), key=lambda kv: (kv[1], entries[kv[0]][0] == team, entries[kv[0]][2]))
                if n >= 3:
                    return entries[i][2], entries[i][3]
        named = [e for e in entries if e[0] == team]
        if named:
            best = max(named, key=lambda e: e[2])
            return best[2], best[3]
        return None
