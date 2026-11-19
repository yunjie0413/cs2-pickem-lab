"""Map-specific strength (Step 8): does a team do better on some maps than others?

Each (team, map) pair carries an offset d in map-logit units, on top of the
map win probability the series model gives (series probability turned into a
map probability by independent maps):

    P(A wins map m) = sigmoid(logit(p0) + d'(A, m) - d'(B, m))

d' is the team's offset on that map minus the average of its offsets over
all maps it has played, so offsets only move a team between its own maps;
general over- or under-performance is left to the series model. Offsets are
learned online from map results (d += eta * surprise for the winner, -= for
the loser) and fade toward 0 with time (half-life `half_life` days), since
map pools, rosters and strategies change. Teams are keyed by HLTV team id.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date


@dataclass
class MapOffsets:
    eta: float                     # learning rate (map-logit units per unit of surprise)
    half_life: float = math.inf    # days for an offset to halve without new results
    d: dict = field(default_factory=dict)   # team id -> {map: (value, date of last change)}

    def _faded(self, entry, on: date) -> float:
        value, last = entry
        if math.isfinite(self.half_life):
            value *= 0.5 ** (max((on - last).days, 0) / self.half_life)
        return value

    def offset(self, team: str, game_map: str, on: date) -> float:
        """Centred offset d'(team, map) on a date."""
        maps = self.d.get(team)
        if not maps:
            return 0.0
        vals = {m: self._faded(e, on) for m, e in maps.items()}
        return vals.get(game_map, 0.0) - sum(vals.values()) / len(vals)

    def predict(self, p0: float, team_a: str, team_b: str, game_map: str, on: date) -> float:
        p0 = min(max(p0, 1e-6), 1 - 1e-6)
        x = math.log(p0 / (1 - p0)) + self.offset(team_a, game_map, on) - self.offset(team_b, game_map, on)
        return 1.0 / (1.0 + math.exp(-x))

    def update(self, team_a: str, team_b: str, game_map: str, on: date, a_won: bool, p: float) -> None:
        surprise = (1.0 if a_won else 0.0) - p
        for team, sign in ((team_a, 1.0), (team_b, -1.0)):
            maps = self.d.setdefault(team, {})
            old = self._faded(maps[game_map], on) if game_map in maps else 0.0
            maps[game_map] = (old + sign * self.eta * surprise, on)
