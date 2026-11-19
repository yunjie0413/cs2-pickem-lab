"""Model v1: our own rating from match results, later blended with VRS points.

The rating engine walks through every match in date order. For each match:
  1. Find each side's team: by lineup when known (3+ of the five players in
     a team's latest lineup means the same team, so renames don't break a
     team's history), otherwise the team that currently uses the name.
  2. Before predicting: adjust for inactivity (time decay) and for lineup
     changes (roster reset).
  3. Predict P(side A wins) from the rating gap plus region offsets,
     flattened by both teams' volatility.
  4. Store that prediction (it used only earlier matches), then update.

Factors (decision 0005) and the parameters that switch each one off:
  time decay .............. decay_days = forget_days = inf
  roster reset ............ roster_reset = roster_new = 0
  LAN weighting ........... w_lan = 1   (LAN status from HLTV only, see below)
  region calibration ...... k_region = 0
  per-team volatility ..... vol_rate = 0

Two kinds of adjustment for inactivity and lineup changes:
  - pull the rating part of the way toward the average (decay_days,
    roster_reset): "we expect the team to be more ordinary now";
  - forget part of the team's match count (forget_days, roster_new), so
    the larger "new team" update size comes back: "we are less sure, so
    learn faster from the next results".
"The average" is the current average rating of all teams; new teams
start there too. It is tracked rather than fixed, because updates are not
zero-sum (a team with few matches moves more than its opponent), so the
average drifts. (An early version decayed ratings toward a fixed 1500
while new teams started at 500: ratings "decayed" upward.)

LAN status comes only from HLTV's list of LAN maps, never from Valve's
files: Valve shows LAN/online (and an event weight) only on a team's "ten
best" wins, a list that depends on results after the match, so using it
leaks the future into the backtest (Step 6, decision 0006). Event-strength
weighting is left out for the same reason until there is a clean source.

The blend with VRS points and the probability calibration happen in a
separate logistic layer (see scripts/fit_model_v1.py).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable, Sequence

MEAN = 1500.0                     # rating of the very first team; the average drifts from here
LN10_400 = math.log(10) / 400.0


@dataclass(frozen=True)
class Params:
    k: float = 32.0              # base update size (rating points)
    k_new: float = 2.0           # K multiplier for teams with few matches, fading to 1 as they play
    decay_days: float = 365.0    # inactivity: gap to the average shrinks by exp(-days / decay_days)
    forget_days: float = math.inf  # inactivity: match count shrinks by exp(-days / forget_days)
    roster_reset: float = 0.0    # fraction of the gap to the average removed when all 5 players change
    roster_new: float = 0.0      # fraction of the match count forgotten when all 5 change
    w_lan: float = 1.0           # update weight of LAN matches between top-50 teams (HLTV); others 1
    k_region: float = 0.0        # learning rate of region offsets
    vol_rate: float = 0.0        # learning rate of per-team volatility
    vol_shrink: float = 0.05     # pull of volatility back toward 0 at each update

    def without(self, factor: str) -> "Params":
        """Same parameters with one factor switched off (for ablation tests)."""
        off = {
            "time_decay": {"decay_days": math.inf, "forget_days": math.inf},
            "roster_reset": {"roster_reset": 0.0, "roster_new": 0.0},
            "lan": {"w_lan": 1.0},
            "region": {"k_region": 0.0},
            "volatility": {"vol_rate": 0.0},
        }[factor]
        return replace(self, **off)


@dataclass
class Team:
    name: str          # latest name used
    rating: float
    lineup: frozenset[str] | None = None
    last: date | None = None
    n: float = 0.0     # matches played (partly forgotten after inactivity / roster changes)
    vol: float = 0.0
    played: int = 0    # matches credited to this team, never forgotten (for display)


@dataclass(frozen=True)
class MatchIn:
    """One match as the engine needs it. Side A is the winner."""
    date: date
    winner: str
    loser: str
    winner_lineup: Sequence[str] | None
    loser_lineup: Sequence[str] | None
    lan: bool | None = None      # True = LAN match between top-50 teams (from HLTV); None = not known


@dataclass(frozen=True)
class Prediction:
    """What the engine knew right before the match (side A = actual winner)."""
    date: date
    team_a: int
    team_b: int
    z: float          # logit of P(A wins) before calibration
    rating_a: float   # effective ratings (incl. region offset)
    rating_b: float
    n_a: int          # matches played before this one (after any forgetting)
    n_b: int


def _norm(lineup: Sequence[str] | None) -> frozenset[str] | None:
    return frozenset(p.lower() for p in lineup) if lineup else None


class Engine:
    def __init__(self, params: Params, regions: dict[str, str] | None = None):
        self.p = params
        self.regions = regions or {}           # team name -> region (from VRS pages)
        self.teams: list[Team] = []
        self.by_name: dict[str, int] = {}
        self.by_player: dict[str, int] = {}
        self.region_offset: Counter = Counter()
        self.total = 0.0                       # sum of all teams' ratings

    def mean(self) -> float:
        """Current average rating of all teams: where new teams start and resets pull to."""
        return self.total / len(self.teams) if self.teams else MEAN

    def _new_team(self, name: str) -> int:
        r = self.mean()
        self.teams.append(Team(name=name, rating=r))
        self.total += r
        tid = len(self.teams) - 1
        self.by_name[name] = tid
        return tid

    def _set(self, t: Team, rating: float) -> None:
        self.total += rating - t.rating
        t.rating = rating

    # --- team identity ------------------------------------------------------
    def find(self, name: str, lineup: frozenset[str] | None) -> tuple[int | None, int]:
        """(existing team id or None, players changed since that team's latest lineup).

        Same team = 3+ of the five players are in that team's *latest* lineup
        (this follows renames). Otherwise, the team that currently goes by
        this name. Where a player played before is not enough on its own: an
        earlier version matched on "3+ players whose last team was X", so two
        new teams built from X's former players could both claim X, and their
        results were mixed into one rating (found with Eternal Fire and
        Walczaki, Step 6).
        """
        if lineup:
            best, best_n = None, 0
            for tid in {self.by_player[p] for p in lineup if p in self.by_player}:
                cur = self.teams[tid].lineup
                n = len(lineup & cur) if cur else 0
                if n > best_n or (n == best_n and best is not None and self.teams[tid].name == name):
                    best, best_n = tid, n
            if best is not None and best_n >= 3:
                return best, 5 - best_n
        tid = self.by_name.get(name)
        if tid is not None and self.teams[tid].name == name:
            old = self.teams[tid].lineup
            changed = 5 - len(old & lineup) if (old and lineup) else 0
            return tid, max(changed, 0)
        return None, 0

    def resolve(self, name: str, lineup: frozenset[str] | None) -> tuple[int, int]:
        """Like find, but creates a new team when there is none."""
        tid, changed = self.find(name, lineup)
        return (self._new_team(name), 0) if tid is None else (tid, changed)

    def region_of(self, t: Team) -> str | None:
        return self.regions.get(t.name)

    def effective(self, t: Team) -> float:
        r = self.region_of(t)
        return t.rating + (self.region_offset[r] if r else 0.0)

    # --- one match ----------------------------------------------------------
    def _prepare(self, tid: int, changed: int, d: date) -> None:
        t, p = self.teams[tid], self.p
        mu = self.mean()
        if t.last is not None:
            days = (d - t.last).days
            if days > 0:
                if math.isfinite(p.decay_days):
                    self._set(t, mu + (t.rating - mu) * math.exp(-days / p.decay_days))
                if math.isfinite(p.forget_days):
                    t.n *= math.exp(-days / p.forget_days)
        if changed > 0:
            frac = min(changed, 5) / 5
            if p.roster_reset > 0:
                self._set(t, mu + (t.rating - mu) * (1 - p.roster_reset * frac))
            if p.roster_new > 0:
                t.n *= 1 - p.roster_new * frac

    def _k(self, t: Team) -> float:
        return self.p.k * (1 + (self.p.k_new - 1) * math.exp(-t.n / 10))

    def _weight(self, m: MatchIn) -> float:
        return self.p.w_lan if m.lan else 1.0

    def process(self, m: MatchIn) -> Prediction:
        la, lb = _norm(m.winner_lineup), _norm(m.loser_lineup)
        a, ca = self.resolve(m.winner, la)
        b, cb = self.resolve(m.loser, lb)
        if a == b:  # both sides resolved to one team (bad data); treat the loser as new
            b, cb = self._new_team(m.loser), 0
        self._prepare(a, ca, m.date)
        self._prepare(b, cb, m.date)
        A, B = self.teams[a], self.teams[b]
        ra, rb = self.effective(A), self.effective(B)
        z = LN10_400 * (ra - rb) * math.exp(-(A.vol + B.vol))
        pred = Prediction(m.date, a, b, z, ra, rb, round(A.n), round(B.n))

        # Update (A won, so the surprise is 1 - P(A wins)).
        p_a = 1.0 / (1.0 + math.exp(-z))
        surprise = 1.0 - p_a
        w = self._weight(m)
        self._set(A, A.rating + self._k(A) * w * surprise)
        self._set(B, B.rating - self._k(B) * w * surprise)
        reg_a, reg_b = self.region_of(A), self.region_of(B)
        if self.p.k_region and reg_a and reg_b and reg_a != reg_b:
            self.region_offset[reg_a] += self.p.k_region * w * surprise
            self.region_offset[reg_b] -= self.p.k_region * w * surprise
        if self.p.vol_rate:
            g = surprise * (-z)  # gradient of the log-likelihood w.r.t. each volatility
            for t in (A, B):
                t.vol = min(1.5, max(-0.5, t.vol + self.p.vol_rate * (g - self.p.vol_shrink * t.vol)))
        for tid, t, lineup, name in ((a, A, la, m.winner), (b, B, lb, m.loser)):
            t.n += 1
            t.played += 1
            t.last = m.date
            t.name = name  # latest name: used for the region and for finding the team by name
            if lineup:
                t.lineup = lineup
                for player in lineup:
                    self.by_player[player] = tid
            self.by_name[name] = tid
        return pred

    def run(self, matches: Iterable[MatchIn]) -> list[Prediction]:
        return [self.process(m) for m in matches]


# --- calibration layer --------------------------------------------------------

def fit_logistic(X: "np.ndarray", iters: int = 50, ridge: float = 1e-6):
    """Weights w maximising sum log sigmoid(X @ w), by Newton's method.

    Every row is written from the actual winner's side (features are
    winner-minus-loser gaps), so the target is always 1. There is no
    intercept on purpose: swapping the two sides must flip the probability.
    """
    import numpy as np
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        s = 1.0 / (1.0 + np.exp(-(X @ w)))
        grad = X.T @ (1 - s) - ridge * w
        H = (X * (s * (1 - s))[:, None]).T @ X + ridge * np.eye(X.shape[1])
        step = np.linalg.solve(H, grad)
        w += step
        if np.abs(step).max() < 1e-9:
            break
    return w
