"""Pick'Em ballots: grading against simulations and choosing a ballot.

A Swiss-stage ballot (current Valve Majors) has 10 picks:
  * 2 teams that will finish 3-0
  * 6 teams that will advance with 3-1 or 3-2 (a team that goes 3-0 does NOT
    count for these picks)
  * 2 teams that will finish 0-3
Each team can be used once. 5 or more correct picks completes the stage.
These numbers live in BallotRules so they can be changed if an event differs.

Two ways to choose a ballot (docs/concepts/pickem-objective.md explains both):
  * best_expected():  maximise the expected number of correct picks.
  * best_threshold(): maximise P(correct picks >= 5), which is what the
    Pick'Em actually rewards. This needs the joint simulated outcomes, not
    just per-team probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

import numpy as np

from .swiss import N_TEAMS


@dataclass(frozen=True)
class BallotRules:
    n_perfect: int = 2                      # picks for 3-0
    n_advance: int = 6                      # picks for "advances with 3-1 or 3-2"
    n_winless: int = 2                      # picks for 0-3
    advance_includes_perfect: bool = False  # True if a 3-0 also satisfied an advance pick
    threshold: int = 5                      # correct picks needed to complete the stage


@dataclass(frozen=True)
class Ballot:
    perfect: tuple[int, ...]  # team indices (0 = seed 1)
    advance: tuple[int, ...]
    winless: tuple[int, ...]

    def check(self, rules: BallotRules) -> None:
        picks = self.perfect + self.advance + self.winless
        if (len(self.perfect), len(self.advance), len(self.winless)) != (rules.n_perfect, rules.n_advance, rules.n_winless):
            raise ValueError("ballot has the wrong number of picks for these rules")
        if len(set(picks)) != len(picks):
            raise ValueError("a team is used in more than one pick")
        if not all(0 <= t < N_TEAMS for t in picks):
            raise ValueError("team index out of range")

    def describe(self, teams: Sequence[str]) -> str:
        name = lambda ts: ", ".join(teams[t] for t in ts)
        return f"3-0: {name(self.perfect)} | advance: {name(self.advance)} | 0-3: {name(self.winless)}"


class Grader:
    """Grades ballots against a fixed set of simulated stages.

    codes: (n_sims, 16) array of result codes (wins - losses), as produced by
    pickem.simulate.run(). Every ballot is graded on the same simulations, so
    comparisons between ballots are like-for-like.
    """

    def __init__(self, codes: np.ndarray, rules: BallotRules = BallotRules()):
        self.rules = rules
        self.hit_perfect = codes == 3
        self.hit_winless = codes == -3
        adv = (codes == 2) | (codes == 1)
        if rules.advance_includes_perfect:
            adv |= codes == 3
        self.hit_advance = adv
        self.n_sims = codes.shape[0]

    def hits(self, ballot: Ballot) -> np.ndarray:
        """Number of correct picks in each simulated stage, shape (n_sims,)."""
        ballot.check(self.rules)
        h = self.hit_perfect[:, list(ballot.perfect)].sum(axis=1)
        h += self.hit_advance[:, list(ballot.advance)].sum(axis=1)
        h += self.hit_winless[:, list(ballot.winless)].sum(axis=1)
        return h

    def p_success(self, ballot: Ballot) -> float:
        """P(correct picks >= threshold): the fraction of simulations where it passes."""
        return float((self.hits(ballot) >= self.rules.threshold).mean())

    def expected(self, ballot: Ballot) -> float:
        return float(self.hits(ballot).mean())

    def distribution(self, ballot: Ballot) -> np.ndarray:
        """P(exactly k correct) for k = 0..10."""
        total = self.rules.n_perfect + self.rules.n_advance + self.rules.n_winless
        return np.bincount(self.hits(ballot), minlength=total + 1) / self.n_sims

    def marginals(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Per-team P(pick would be correct) for the 3-0, advance and 0-3 slots."""
        return self.hit_perfect.mean(0), self.hit_advance.mean(0), self.hit_winless.mean(0)


def best_expected(grader: Grader) -> Ballot:
    """Ballot with the highest expected number of correct picks (exact).

    Expected correct picks = sum of each pick's own probability, so only the
    per-team marginals matter. We enumerate every choice of 3-0 and 0-3 teams
    and fill the advance slots with the best remaining teams.
    """
    r = grader.rules
    mp, ma, mw = grader.marginals()
    best, best_score = None, -1.0
    for P in combinations(range(N_TEAMS), r.n_perfect):
        rest = [t for t in range(N_TEAMS) if t not in P]
        for W in combinations(rest, r.n_winless):
            pool = sorted((t for t in rest if t not in W), key=lambda t: -ma[t])
            A = tuple(sorted(pool[: r.n_advance]))
            score = mp[list(P)].sum() + mw[list(W)].sum() + ma[list(A)].sum()
            if score > best_score:
                best, best_score = Ballot(P, A, W), score
    return best


def best_threshold(
    grader: Grader,
    k_perfect: int = 6,
    k_winless: int = 6,
    k_advance: int = 10,
    top: int = 20,
) -> list[tuple[Ballot, float]]:
    """Ballots with the highest P(correct >= threshold), best first.

    Search space: the full space has about 10 million ballots, so we restrict
    each slot to its most promising candidates (the top k teams by that
    slot's marginal probability) and enumerate every ballot built from them.
    A team with a low chance of going 3-0 is essentially never worth a 3-0
    pick, so this loses little. Raise the k values to search wider.

    Returns the ``top`` ballots with their success probability *on these
    simulations*. Picking the maximum of many noisy estimates overstates it
    (winner's curse), so re-grade the finalists on fresh simulations with
    confirm() before trusting the number.
    """
    r = grader.rules
    mp, ma, mw = grader.marginals()
    cand_p = [int(t) for t in np.argsort(-mp)[:k_perfect]]
    cand_w = [int(t) for t in np.argsort(-mw)[:k_winless]]
    cand_a = [int(t) for t in np.argsort(-ma)[:k_advance]]

    # Hits from every possible set of advance picks, computed once:
    # adv_sums[s, j] = correct advance picks of subset j in simulation s.
    subsets = list(combinations(cand_a, r.n_advance))
    indicator = np.zeros((len(cand_a), len(subsets)), dtype=np.float32)
    for j, sub in enumerate(subsets):
        for t in sub:
            indicator[cand_a.index(t), j] = 1.0
    adv_sums = (grader.hit_advance[:, cand_a].astype(np.float32) @ indicator).astype(np.int8)
    subset_sets = [set(s) for s in subsets]

    results: list[tuple[float, Ballot]] = []
    for P in combinations(cand_p, r.n_perfect):
        base_p = grader.hit_perfect[:, list(P)].sum(axis=1)
        for W in combinations([t for t in cand_w if t not in P], r.n_winless):
            used = set(P) | set(W)
            valid = [j for j, s in enumerate(subset_sets) if not (s & used)]
            if not valid:
                continue
            base = (base_p + grader.hit_winless[:, list(W)].sum(axis=1)).astype(np.int8)
            ok = (adv_sums[:, valid] + base[:, None]) >= r.threshold
            probs = ok.mean(axis=0)
            for j, pr in zip(valid, probs):
                results.append((float(pr), Ballot(tuple(sorted(P)), tuple(sorted(subsets[j])), tuple(sorted(W)))))
    results.sort(key=lambda x: -x[0])
    return [(b, p) for p, b in results[:top]]


def confirm(ballots: Sequence[Ballot], fresh: Grader) -> list[tuple[Ballot, float]]:
    """Re-grade candidate ballots on independent simulations, best first."""
    scored = [(b, fresh.p_success(b)) for b in ballots]
    return sorted(scored, key=lambda x: -x[1])
