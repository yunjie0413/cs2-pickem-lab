# CS2 Pick'Em Lab

Predicts CS2 Major Swiss stages and chooses the Pick'Em ballot with the best
chance of 5+ correct picks.

**Status:** the Swiss simulator and ballot optimizer are done and tested.
The match model is still a placeholder (Baseline 0: Valve's VRS points),
so the output is **not a real prediction yet**.

## How it works

```
match model                 tournament layer              ballot layer
P(A beats B), BO1/BO3  -->  Valve Swiss rules, played  --> grade every candidate ballot
(pickem/baseline.py;        100k times                     in every simulated stage;
 real model to come)        (pickem/swiss.py,              pick max P(>=5 correct)
                             pickem/simulate.py)           (pickem/ballot.py)
```

## Run it

Requires Python 3.11+ and numpy (`pip install numpy pytest`).

```bash
python scripts/run_stage.py data/events/singapore-2026-stage1.json
```

```bash
python -m pytest
```

## Reading the project record

- [docs/JOURNAL.md](docs/JOURNAL.md): every step in order, with results and open questions. **Start here.**
- [docs/decisions/](docs/decisions/): one file per lasting decision and the reasons for it.
- [docs/concepts/pickem-objective.md](docs/concepts/pickem-objective.md): why P(≥5) differs from expected correct picks.
- [docs/concepts/swiss-rules.md](docs/concepts/swiss-rules.md): Valve's rules mapped to the code.

## Layout

```
pickem/swiss.py      Valve Swiss pairing rules, one simulated stage
pickem/simulate.py   Monte Carlo over many stages
pickem/ballot.py     Pick'Em rules, grading, optimizers
pickem/baseline.py   Baseline 0 match model (VRS points -> Elo)
data/events/         Event files: teams, seeds, completed matches
scripts/run_stage.py End-to-end run for one event file
tests/               pytest suite
```

The earlier Codex JavaScript prototype is still in `main`'s history (commit `ec07644`).
