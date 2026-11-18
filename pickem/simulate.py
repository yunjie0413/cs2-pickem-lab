"""Monte Carlo layer: play a Swiss stage many times and keep every outcome.

Why keep every simulated outcome instead of only per-team probabilities?
A Pick'Em ballot is graded on the *joint* outcome of the stage (see
docs/concepts/pickem-objective.md). Keeping the full (n_sims x 16) table of
records lets the ballot module grade any ballot on exactly the same
simulated tournaments.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

import numpy as np

from .swiss import CODE_LABEL, N_TEAMS, simulate_stage

# Optional per-simulation parameter draw: returns (p_bo1, p_bo3) for one
# simulated tournament. Used to model uncertainty about team strength itself
# (a team that is underrated stays underrated for the whole stage).
Sampler = Callable[[np.random.Generator], tuple[np.ndarray, np.ndarray]]

RESULT_ORDER = (3, 2, 1, -1, -2, -3)  # 3-0, 3-1, 3-2, 2-3, 1-3, 0-3


@dataclass
class SimulationResult:
    teams: list[str]   # team names in seed order (index 0 = seed 1)
    codes: np.ndarray  # (n_sims, 16) int8, wins - losses per team per simulation

    @property
    def n_sims(self) -> int:
        return self.codes.shape[0]

    def probabilities(self) -> np.ndarray:
        """(16, 6) array: P(team finishes with each record), RESULT_ORDER columns."""
        return np.stack([(self.codes == c).mean(axis=0) for c in RESULT_ORDER], axis=1)

    def table(self) -> str:
        """Human-readable per-team finish probabilities."""
        probs = self.probabilities()
        head = f"{'seed':>4}  {'team':<20}" + "".join(f"{CODE_LABEL[c]:>7}" for c in RESULT_ORDER) + f"{'adv':>7}"
        lines = [head, "-" * len(head)]
        for i, name in enumerate(self.teams):
            row = probs[i]
            adv = row[:3].sum()
            lines.append(f"{i + 1:>4}  {name:<20}" + "".join(f"{x:>7.1%}" for x in row) + f"{adv:>7.1%}")
        lines.append(f"({self.n_sims:,} simulated stages)")
        return "\n".join(lines)


def run(
    teams: Sequence[str],
    p_bo1: np.ndarray,
    p_bo3: np.ndarray,
    n_sims: int = 100_000,
    seed: int = 0,
    fixed: Mapping[tuple[int, int], int] | None = None,
    sampler: Sampler | None = None,
) -> SimulationResult:
    """Simulate ``n_sims`` stages. Same inputs + same seed = identical output.

    If ``sampler`` is given it is called once per simulated stage to draw that
    stage's probability matrices; otherwise p_bo1 / p_bo3 are used throughout.
    """
    if len(teams) != N_TEAMS:
        raise ValueError(f"need {N_TEAMS} teams, got {len(teams)}")
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    p1, p3 = np.asarray(p_bo1).tolist(), np.asarray(p_bo3).tolist()  # lists are faster to index
    codes = np.empty((n_sims, N_TEAMS), dtype=np.int8)
    for s in range(n_sims):
        if sampler is not None:
            a, b = sampler(np_rng)
            p1, p3 = np.asarray(a).tolist(), np.asarray(b).tolist()
        codes[s] = simulate_stage(p1, p3, rng, fixed)
    return SimulationResult(list(teams), codes)
