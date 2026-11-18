"""Valve Major Swiss stage: pairing rules and a single-stage simulation.

Rules are transcribed from Valve's Major Supplemental Rulebook
(github.com/ValveSoftware/counter-strike_rules_and_regs, commit 621b7d9,
2026-10-07). docs/concepts/swiss-rules.md quotes the rule text and maps each
rule to the function that implements it.

Conventions used throughout the project
---------------------------------------
* A team is referred to by its initial seed index: 0 = seed 1, ..., 15 = seed 16.
* A team's final result is encoded as ``wins - losses``:
  3-0 -> +3, 3-1 -> +2, 3-2 -> +1, 2-3 -> -1, 1-3 -> -2, 0-3 -> -3.
  The six values are distinct, so one small integer stores the full record.
"""
from __future__ import annotations

import random
from typing import Callable, Mapping, Sequence

N_TEAMS = 16
WINS_TO_ADVANCE = 3
LOSSES_TO_ELIMINATE = 3

# Rulebook "Initial Swiss Match-ups": seed 1 v 9, 2 v 10, ..., 8 v 16.
ROUND1_PAIRS = tuple((i, i + 8) for i in range(8))

# Rulebook priority table for rounds 4 and 5 (pools of exactly 6 teams).
# Numbers are 1-based positions in the pool sorted by mid-stage seed.
# "Select the top-most row that does not result in a rematch."
PRIORITY_TABLE = (
    ((1, 6), (2, 5), (3, 4)),
    ((1, 6), (2, 4), (3, 5)),
    ((1, 5), (2, 6), (3, 4)),
    ((1, 5), (2, 4), (3, 6)),
    ((1, 4), (2, 6), (3, 5)),
    ((1, 4), (2, 5), (3, 6)),
    ((1, 6), (2, 3), (4, 5)),
    ((1, 5), (2, 3), (4, 6)),
    ((1, 3), (2, 6), (4, 5)),
    ((1, 3), (2, 5), (4, 6)),
    ((1, 4), (2, 3), (5, 6)),
    ((1, 3), (2, 4), (5, 6)),
    ((1, 2), (3, 6), (4, 5)),
    ((1, 2), (3, 5), (4, 6)),
    ((1, 2), (3, 4), (5, 6)),
)

RECORD_CODE = {(3, 0): 3, (3, 1): 2, (3, 2): 1, (2, 3): -1, (1, 3): -2, (0, 3): -3}
CODE_LABEL = {3: "3-0", 2: "3-1", 1: "3-2", -1: "2-3", -2: "1-3", -3: "0-3"}

# Probability lookup: p[a][b] = P(team a beats team b) in that format.
ProbMatrix = Sequence[Sequence[float]]


def is_best_of_three(wins: int, losses: int) -> bool:
    """Rulebook: elimination and advancement matches are BO3, all others BO1.

    A match is an advancement match when both teams have 2 wins and an
    elimination match when both have 2 losses (teams in a match always share
    a record, so checking one team is enough).
    """
    return wins == WINS_TO_ADVANCE - 1 or losses == LOSSES_TO_ELIMINATE - 1


def _pair_high_vs_low(order: list[int], have_met: Callable[[int, int], bool]) -> list[tuple[int, int]] | None:
    """Rounds 2-3: highest seed plays the lowest seed that is not a rematch.

    ``order`` lists the pool from highest to lowest mid-stage seed. The rule
    is applied greedily; if a greedy choice later leaves two teams who already
    met, we backtrack to the next-lowest opponent. (The rulebook doesn't say
    what to do at a dead end; backtracking is the natural reading of "if
    possible". It almost never triggers.) Returns None if no rematch-free
    pairing exists.
    """
    if not order:
        return []
    top, rest = order[0], order[1:]
    for opp in reversed(rest):
        if have_met(top, opp):
            continue
        sub = _pair_high_vs_low([t for t in rest if t != opp], have_met)
        if sub is not None:
            return [(top, opp)] + sub
    return None


def _pair_by_priority_table(order: list[int], have_met: Callable[[int, int], bool]) -> list[tuple[int, int]]:
    """Rounds 4-5: first row of PRIORITY_TABLE with no rematch."""
    if len(order) != 6:
        raise ValueError(f"priority table needs a pool of 6, got {len(order)}")
    for row in PRIORITY_TABLE:
        pairs = [(order[a - 1], order[b - 1]) for a, b in row]
        if not any(have_met(x, y) for x, y in pairs):
            return pairs
    # No rematch-free row exists ("if possible" fails): fall back to row 1.
    return [(order[a - 1], order[b - 1]) for a, b in PRIORITY_TABLE[0]]


class SwissState:
    """Records, opponents and pairing logic for one 16-team Swiss stage."""

    def __init__(self) -> None:
        self.wins = [0] * N_TEAMS
        self.losses = [0] * N_TEAMS
        self.opponents: list[list[int]] = [[] for _ in range(N_TEAMS)]
        self.rounds_played = 0

    # --- bookkeeping -----------------------------------------------------
    def is_active(self, t: int) -> bool:
        return self.wins[t] < WINS_TO_ADVANCE and self.losses[t] < LOSSES_TO_ELIMINATE

    def is_finished(self) -> bool:
        return not any(self.is_active(t) for t in range(N_TEAMS))

    def have_met(self, a: int, b: int) -> bool:
        return b in self.opponents[a]

    def buchholz(self, t: int) -> int:
        """Rulebook Difficulty Score: sum of (wins - losses) of every opponent faced."""
        return sum(self.wins[o] - self.losses[o] for o in self.opponents[t])

    def record_result(self, winner: int, loser: int) -> None:
        self.wins[winner] += 1
        self.losses[loser] += 1
        self.opponents[winner].append(loser)
        self.opponents[loser].append(winner)

    # --- pairing ---------------------------------------------------------
    def pools(self) -> dict[tuple[int, int], list[int]]:
        """Active teams grouped by record, each pool sorted by mid-stage seed.

        Rulebook "Mid-stage Seed Calculation": record, then Difficulty Score
        (higher is better), then initial seed. Within a pool the record is
        equal, so the sort key is (-buchholz, initial seed).
        """
        pools: dict[tuple[int, int], list[int]] = {}
        for t in range(N_TEAMS):
            if self.is_active(t):
                pools.setdefault((self.wins[t], self.losses[t]), []).append(t)
        for key in pools:
            pools[key].sort(key=lambda t: (-self.buchholz(t), t))
        return pools

    def next_pairings(self) -> list[tuple[int, int]]:
        """Pairings for the next round; each pair is (higher seed, lower seed)."""
        rnd = self.rounds_played + 1
        if rnd == 1:
            return list(ROUND1_PAIRS)
        pairs: list[tuple[int, int]] = []
        # Highest record first, so the output order is stable and readable.
        for _, order in sorted(self.pools().items(), key=lambda kv: (-kv[0][0], kv[0][1])):
            if rnd in (2, 3):
                p = _pair_high_vs_low(order, self.have_met)
                if p is None:  # no rematch-free pairing exists: plain high vs low
                    p = [(order[i], order[-1 - i]) for i in range(len(order) // 2)]
            else:
                p = _pair_by_priority_table(order, self.have_met)
            pairs.extend(p)
        return pairs

    def result_codes(self) -> list[int]:
        return [RECORD_CODE[(self.wins[t], self.losses[t])] for t in range(N_TEAMS)]


def simulate_stage(
    p_bo1: ProbMatrix,
    p_bo3: ProbMatrix,
    rng: random.Random,
    fixed: Mapping[tuple[int, int], int] | None = None,
    log: list | None = None,
) -> list[int]:
    """Play one full Swiss stage and return each team's result code.

    p_bo1 / p_bo3: P(row team beats column team) in a BO1 / BO3.
    fixed: results that already happened, keyed by (lower index, higher index)
        -> winner index. Pairings are deterministic given results, so real
        results reproduce the real bracket and are used instead of a coin flip.
    log: if given, one (round, team_a, team_b, best_of, winner) tuple is
        appended per match. Useful for tests and debugging.
    """
    state = SwissState()
    while not state.is_finished():
        rnd = state.rounds_played + 1
        for a, b in state.next_pairings():
            bo3 = is_best_of_three(state.wins[a], state.losses[a])
            key = (a, b) if a < b else (b, a)
            if fixed is not None and key in fixed:
                winner = fixed[key]
            else:
                p = p_bo3[a][b] if bo3 else p_bo1[a][b]
                winner = a if rng.random() < p else b
            loser = b if winner == a else a
            state.record_result(winner, loser)
            if log is not None:
                log.append((rnd, a, b, 3 if bo3 else 1, winner))
        state.rounds_played += 1
    return state.result_codes()
