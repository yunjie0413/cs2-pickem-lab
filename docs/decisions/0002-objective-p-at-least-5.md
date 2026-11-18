# 0002: Optimize P(≥5 correct), not expected correct picks

Date: 2026-11-18. Status: accepted (user's choice).

## Context
The Pick'Em completes a stage at 5+ correct picks out of 10. More correct
picks earn nothing extra.

## Decision
`best_threshold()` maximizes the fraction of simulated stages where the
ballot gets ≥5 correct. `best_expected()` is kept as a comparison.

## Details
- The search is restricted to the top candidates per slot (6 / 10 / 6),
  about 40k ballots, all graded exactly on the same simulations.
- The top 20 are re-graded on fresh, independent simulations to remove the
  winner's-curse bias, and the best of those is reported.

## Consequences
- When the model is flat (Baseline 0), both objectives choose nearly the same
  ballot. Expected to diverge with a sharper model.
- If an event changes the scoring (threshold, slot counts, whether a 3-0
  counts as an advance), change `BallotRules`, not the optimizer.
