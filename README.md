# CS2 Pick'Em Lab

Predicts CS2 Major Swiss stages and chooses the Pick'Em ballot with the best
chance of 5+ correct picks.

**Status:** the Swiss simulator, ballot optimizer and Model v1 are done and
tested. Model v1 is our own Elo-style rating blended with Valve's VRS
points, BO1/BO3 calibrated on real matches of each format (log loss 0.6547
vs 0.6605 for Valve's points alone on validation matches). Six extra
factors (region, time decay, roster reset, LAN, volatility, HLTV player
ratings) were tested by backward elimination and none cleared the bar
(journal Step 7a, decision 0007). Strength uncertainty was measured at zero
(Step 7b), and map-specific strength showed no effect (Step 8). A backtest on
four past Major Stage 1s found predicted pass rates in line with what
happened. It found no detectable difference from Valve's points alone
(Step 7c). Scored once on the test period (1,440 matches from 2025-11),
Model v1 beats Valve's points by 0.011 ± 0.003 log loss per match.

**Final Singapore Stage 1 picks** (journal Step 9; P(≥5 correct) ≈ 25%):
3-0 PVISION, 100 Thieves | advance Ninjas in Pyjamas, HEROIC, FaZe,
Eternal Fire, 9z, M80 | 0-3 GOSH, Chinggis Warriors.

## How it works

```
match model                 tournament layer              ballot layer
P(A beats B), BO1/BO3  -->  Valve Swiss rules, played  --> grade every candidate ballot
(pickem/model_v1.py,        100k times                     in every simulated stage;
 pickem/predict.py)         (pickem/swiss.py,              pick max P(>=5 correct)
                             pickem/simulate.py)           (pickem/ballot.py)
```

## Run it

Requires Python 3.11+ and numpy (`pip install numpy pytest`). Works on
Windows, macOS and Linux.

Once, to download Valve's data (~300 MB, not committed) and build the match list:

```bash
python scripts/fetch_vrs.py
```

```bash
python scripts/build_matches.py
```

Then fit Model v1 (a few minutes) and, if the HLTV file is present, the
BO1/BO3 calibration:

```bash
python scripts/fit_model_v1.py
```

```bash
python scripts/check_bo_format.py
```

and the spread of team strength per event for the simulator (Step 7; also
needs the HLTV file):

```bash
python scripts/fit_uncertainty.py
```

Simulate a stage and choose a ballot (add `--model baseline` for Baseline 0,
`--sigma X` to set the strength spread by hand):

```bash
python scripts/run_stage.py data/events/singapore-2026-stage1.json
```

Backtest on past Majors' Stage 1 (event files in `data/events/past/`,
rebuilt by `scripts/build_past_events.py`):

```bash
python scripts/backtest_majors.py
```

```bash
python scripts/eval_baseline.py
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
pickem/swiss.py            Valve Swiss pairing rules, one simulated stage
pickem/simulate.py         Monte Carlo over many stages
pickem/ballot.py           Pick'Em rules, grading, optimizers
pickem/baseline.py         Baseline 0 match model (VRS points -> Elo)
pickem/model_v1.py         Model v1 rating engine (own Elo-style rating + factors)
pickem/history.py          Valve match list + HLTV LAN links, as the engine reads them
pickem/predict.py          Model v1 -> BO1/BO3 win probabilities for an event
pickem/evaluate.py         Scores: log loss, Brier, calibration; VRS points lookup
pickem/data/vrs.py         Parser for Valve's VRS snapshot pages
pickem/data/hltv.py        HLTV map list -> series (BO1/BO3/BO5) -> links to Valve's matches
data/events/               Event files: teams, seeds, rosters, completed matches
scripts/run_stage.py       End-to-end run for one event file
scripts/backtest_majors.py Replay past Major Stage 1s and grade the ballots
scripts/fit_model_v1.py    Tune Model v1, test each factor, compare with Baseline 0
scripts/check_bo_format.py BO1 vs BO3 calibration from HLTV-linked matches
tests/                     pytest suite
```

HLTV data (`data/raw/hltv/maps_lan_top50.csv`) was collected once in the
user's own logged-in browser and is not committed (it is HLTV's data). Without
it, everything runs; LAN status and the BO1/BO3 check are then skipped.

The earlier Codex JavaScript prototype is still in `main`'s history (commit `ec07644`).
