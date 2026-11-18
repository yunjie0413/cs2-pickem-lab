# 0001: Two separate layers, and Monte Carlo instead of DP

Date: 2026-11-18. Status: accepted.

## Context
The first question was "deterministic probability DP, or train weights with
machine learning and then simulate?" That treats one choice as two. There are
two independent layers:

- **Match model:** P(team A beats team B) in a BO1 or BO3. "Formula vs
  machine learning" is a choice made here.
- **Tournament layer:** turning those match probabilities into Swiss stage
  outcomes and ballot scores. "DP vs simulation" is a choice made here.

Any match model works with either tournament method.

## Decision
- Keep the layers in separate modules: `pickem/baseline.py` (and later
  models) → `pickem/swiss.py` + `pickem/simulate.py` → `pickem/ballot.py`.
- Use **Monte Carlo simulation** for the tournament layer.

## Why not DP
1. Valve's pairings depend on the whole history (Difficulty Score, rematch
   avoidance), so a DP state must hold the whole bracket. That's possible but
   complicated, for no real gain.
2. DP naturally produces per-team probabilities. Ballot success needs the
   **joint** outcome (see docs/concepts/pickem-objective.md), so we'd have to
   simulate anyway.
3. DP's exactness is false precision. With 100k simulations the sampling
   error is about ±0.15 percentage points, far smaller than any match model's
   error. With a fixed random seed the simulation also gives identical
   numbers on every run.
4. Uncertainty about team strength (draw a strength once per simulated
   stage) is natural in simulation and awkward in DP.

## Consequences
- 100k simulations take about 8 s in pure Python. Acceptable; we can
  vectorize later if needed.
- Every result depends on the seed and the number of simulations, so scripts
  report both.
