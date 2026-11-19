"""HLTV player ratings by month (Rating 3.0), collected in the user's browser.

The local file data/raw/hltv/players_monthly.csv (gitignored: it is HLTV's
data) has one row per player, calendar month and opponent filter:
  All    every opponent
  Top50  only opponents in HLTV's top 50 at the time of the match
Columns: start, end, filter, player_id, nick, teams, maps, rounds,
net_kills_24, eco_swing, rnd_swing, rating.

PlayerRatings.value(nick, team, on) gives one number per player and date,
on the scale of ratings against top-50 opponents, from the 6 calendar
months before the month of `on` only, so no later result is used.

Rounds against top-50 opponents ("top" rounds, rating r50 over n50) count
fully. Rounds against everyone else ("rest", rating rr over nr, worked out
as All minus Top50) are inflated by weaker opponents and say less about a
player's level against good teams, so they count after subtracting an
inflation gap and with a smaller weight:

    v = (mu0 K + r50 n50 + w nr (rr - delta)) / (K + n50 + w nr)      K = 500 rounds (about 25 maps)

All three numbers are fitted on training months only (before 2025-06),
from the player file alone (no match results):
  delta  gap between rest and top ratings of players with >= 300 rounds of
         both in the same 6 months (journal Step 7a: about +0.09 at every mix)
  w, mu0 from players who moved up: a 6-month window with < 100 top rounds
         and >= 300 rest rounds, then >= 200 top rounds in the next 6
         months. w and mu0 are chosen so v predicts that later top rating
         best (least squares). This is the stand-in / new-signing case,
         selection included.
A player with no rounds at all gets mu0.

Journal Step 7a records why this replaced the first rule (a straight line
from the all-opponent rating, fitted on players with plenty of both kinds of
rounds): for those players most "all" rounds are top rounds, so the line
showed almost no inflation, and a stand-in with only weak opponents counted
as a top player.

Valve's lineups give nicknames only. A nickname is matched to HLTV's player
ID by lowercase name; when two HLTV players share it, the one who played for
a team of the same name in the window wins, then the one with more rounds.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from .hltv import norm_name

K_ROUNDS = 500.0
WINDOW_MONTHS = 6
FIT_BEFORE = date(2025, 6, 1)   # end of the training period: delta, w and mu0 use earlier months only
GAP_MIN_ROUNDS = 300            # delta: rounds needed in both parts of the same window
PROMO_MAX_TOP, PROMO_MIN_REST, PROMO_MIN_TOP_AFTER = 100, 300, 200
W_GRID = [0.0] + [round(0.02 * i, 2) for i in range(1, 51)]  # 0 .. 1
DEFAULTS = (0.0, 1.0, 1.0)      # (delta, w, mu0) when there is too little data to fit (tests)


def _num(s: str) -> float:
    s = s.strip().replace("−", "-").replace("%", "").replace("+", "")
    return float(s) if s else 0.0


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


@dataclass(frozen=True)
class MonthRow:
    month: int      # year * 12 + month - 1
    rounds: int
    rating: float


class PlayerRatings:
    def __init__(self, rows: list[dict]):
        self.months: dict[str, dict[str, list[MonthRow]]] = {"All": defaultdict(list), "Top50": defaultdict(list)}
        self.ids_by_nick: dict[str, set[str]] = defaultdict(set)
        self.team_names: dict[tuple[str, int], set[str]] = defaultdict(set)   # (id, month) -> team names
        first = None
        for r in rows:
            pid, f = r["player_id"], r["filter"]
            if not pid or f not in self.months:
                continue
            mi = _month_index(date.fromisoformat(r["start"]))
            first = mi if first is None else min(first, mi)
            self.months[f][pid].append(MonthRow(mi, int(_num(r["rounds"])), _num(r["rating"])))
            self.ids_by_nick[r["nick"].strip().lower()].add(pid)
            for t in r["teams"].split("|"):
                if t:
                    self.team_names[(pid, mi)].add(norm_name(t))
        self.first_month = first
        self.delta, self.gap_n = self._fit_gap()
        self.w, self.mu0, self.promo_n = self._fit_promotion()
        self._cache: dict[tuple, float] = {}

    # --- windows ------------------------------------------------------------
    def _parts(self, pid: str | None, lo: int, hi: int) -> tuple[float, float, float, float]:
        """(top rounds, top rating, rest rounds, rest rating) over months [lo, hi)."""
        tot = {}
        for f in ("All", "Top50"):
            n = s = 0.0
            for m in (self.months[f].get(pid, ()) if pid else ()):
                if lo <= m.month < hi:
                    n += m.rounds
                    s += m.rounds * m.rating
            tot[f] = (n, s)
        (na, sa), (n5, s5) = tot["All"], tot["Top50"]
        nr = max(na - n5, 0.0)
        return n5, (s5 / n5 if n5 else 0.0), nr, ((sa - s5) / nr if nr else 0.0)

    def window(self, pid: str | None, on: date) -> tuple[float, float, float, float]:
        """(top rounds, top rating, rest rounds, rest rating) in the 6 months before `on`'s month."""
        hi = _month_index(on)
        return self._parts(pid, hi - WINDOW_MONTHS, hi)

    @staticmethod
    def _combine(n5, r5, nr, rr, delta, w, mu0) -> float:
        return (mu0 * K_ROUNDS + r5 * n5 + w * nr * (rr - delta)) / (K_ROUNDS + n5 + w * nr)

    # --- fits on training months ----------------------------------------------
    def _fit_gap(self) -> tuple[float, int]:
        """Mean (rest rating - top rating) over players with plenty of both in the same window."""
        if self.first_month is None:
            return DEFAULTS[0], 0
        cut, gaps = _month_index(FIT_BEFORE), []
        pids = set(self.months["Top50"])
        for hi in range(self.first_month + WINDOW_MONTHS, cut + 1):
            for pid in pids:
                n5, r5, nr, rr = self._parts(pid, hi - WINDOW_MONTHS, hi)
                if n5 >= GAP_MIN_ROUNDS and nr >= GAP_MIN_ROUNDS:
                    gaps.append(rr - r5)
        if len(gaps) < 50:
            return DEFAULTS[0], len(gaps)
        return float(np.mean(gaps)), len(gaps)

    def _fit_promotion(self) -> tuple[float, float, int]:
        """(w, mu0) that best predict the later top rating of players who moved up."""
        if self.first_month is None:
            return DEFAULTS[1], DEFAULTS[2], 0
        cut, pairs = _month_index(FIT_BEFORE), []
        for pid in self.months["All"]:
            for m in range(self.first_month + WINDOW_MONTHS, cut - WINDOW_MONTHS + 1):
                n5, r5, nr, rr = self._parts(pid, m - WINDOW_MONTHS, m)
                if n5 < PROMO_MAX_TOP and nr >= PROMO_MIN_REST:
                    n5b, r5b, _, _ = self._parts(pid, m, m + WINDOW_MONTHS)
                    if n5b >= PROMO_MIN_TOP_AFTER:
                        pairs.append((n5, r5, nr, rr, r5b))
                        break  # one pair per player: the first window where he moved up
        if len(pairs) < 30:
            return DEFAULTS[1], DEFAULTS[2], len(pairs)
        x = np.array(pairs)
        n5, r5, nr, rr, y = x.T
        best = None
        for w in W_GRID:
            d = K_ROUNDS + n5 + w * nr
            a, b = K_ROUNDS / d, (r5 * n5 + w * nr * (rr - self.delta)) / d   # v = mu0 a + b
            mu0 = float(np.sum(a * (y - b)) / np.sum(a * a))
            sse = float(np.sum((y - mu0 * a - b) ** 2))
            if best is None or sse < best[0]:
                best = (sse, w, mu0)
        return best[1], best[2], len(pairs)

    # --- lookups -------------------------------------------------------------
    def resolve(self, nick: str, team: str | None, on: date) -> str | None:
        """HLTV player ID for a Valve nickname, judged on the window before `on`."""
        cands = self.ids_by_nick.get(nick.lower())
        if not cands:
            return None
        if len(cands) == 1:
            return next(iter(cands))
        hi = _month_index(on)
        lo = hi - WINDOW_MONTHS
        tn = norm_name(team) if team else None

        def score(pid: str):
            hit = bool(tn) and any(tn in self.team_names.get((pid, mi), ()) for mi in range(lo, hi))
            rounds = sum(m.rounds for m in self.months["All"].get(pid, ()) if lo <= m.month < hi)
            return hit, rounds, pid

        return max(cands, key=score)

    def value(self, nick: str, team: str | None, on: date) -> float:
        key = (nick.lower(), team, _month_index(on))
        if key not in self._cache:
            n5, r5, nr, rr = self.window(self.resolve(nick, team, on), on)
            self._cache[key] = self._combine(n5, r5, nr, rr, self.delta, self.w, self.mu0)
        return self._cache[key]


def load_players(path: Path) -> PlayerRatings:
    with open(path, newline="", encoding="utf-8") as fp:
        return PlayerRatings(list(csv.DictReader(fp)))
