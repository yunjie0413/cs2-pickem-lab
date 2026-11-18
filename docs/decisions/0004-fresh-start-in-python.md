# 0004: Start fresh, in Python

Date: 2026-11-18. Status: accepted.

## Context
The repository's `main` branch holds a Codex-generated JavaScript web
prototype: fictional teams, hand-typed Elo ratings, a fixed veto heuristic,
no data pipeline and no evaluation.

## Decision
- Rebuild on the `rebuild` branch. The old prototype stays in git history on
  `main` (commit `ec07644`).
- Python + numpy for modelling and simulation; pytest for tests. A website,
  if wanted, comes later on top of output files.
- Every step is recorded in `docs/JOURNAL.md`; every lasting choice gets a
  file in `docs/decisions/`.

## Consequences
- The GitHub Pages workflow is removed on this branch. Merging `rebuild` into
  `main` takes the old site down until a new one exists.
