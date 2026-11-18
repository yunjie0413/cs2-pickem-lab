# Project journal

A dated record of every step: what was done, why, what came out of it, and
what's still open. Newest entries at the bottom. Lasting choices also get a
file in `docs/decisions/`.

---

## 2026-11-18, Step 0: Discussion and scope

**Goal set by the user:** predict the next Major's Stage 1 (PGL Major
Singapore 2026, Stage 1 reported for 24–27 Nov), then extend to all stages
of any Major. The Pick'Em target is P(≥5 correct picks).

**Corrections made during the discussion:**
- "DP vs ML + simulation" mixes two separate choices: the match model
  (formula vs learned weights) and the tournament layer (DP vs Monte Carlo).
  → [decision 0001](decisions/0001-two-layers-and-monte-carlo.md)
- A hand-weighted "combine the factors" formula is a logistic regression with
  guessed weights. Overlapping factors (form, ranking, player ratings) count
  the same strength several times and make it overconfident. Plan: write the
  formula, then fit its few weights on past matches.
- Big ML models (gradient boosting, neural nets) will overfit. There are only
  a few thousand relevant matches per year, with rosters changing.
- Betting markets are the best match predictor available; our match model
  probably won't beat them. The ballot optimizer (joint simulation →
  P(≥5)) is where the clearest edge is.
- An HLTV account doesn't make automated data collection possible (no API,
  terms forbid scraping). → [decision 0003](decisions/0003-data-sources.md)

**Decisions:** [0001](decisions/0001-two-layers-and-monte-carlo.md),
[0002](decisions/0002-objective-p-at-least-5.md),
[0003](decisions/0003-data-sources.md),
[0004](decisions/0004-fresh-start-in-python.md).

---

## 2026-11-18, Step 1: Fresh start, Swiss rules engine

**Done:** removed the Codex prototype on branch `rebuild` (still in `main`'s
history). Wrote `pickem/swiss.py`, which implements Valve's Major Swiss rules
transcribed from the official rulebook (commit `621b7d9`): round 1 pairings,
high-vs-low pairing in rounds 2–3, the 15-row priority table in rounds 4–5,
Buchholz Difficulty Score, BO1/BO3 rules, and fixed results for stages
already in progress.

**Why this first:** the simulator doesn't depend on which match model we
choose. It has to be exactly right, because every number downstream goes
through it.

**Evidence:** `tests/test_swiss.py` checks the rulebook's own Buchholz
example, the record counts every 16-team Swiss must produce (2/3/3/3/3/2),
33 matches with 20 BO1 + 13 BO3 and no rematches, the "higher seed always
wins" bracket, the priority-table fallback and backtracking.
Rules ↔ code mapping: [concepts/swiss-rules.md](concepts/swiss-rules.md).

**Interpretation choices** (rulebook silent): backtracking at dead ends in
rounds 2–3, and fallbacks when no rematch-free pairing exists. Documented in
swiss-rules.md.

---

## 2026-11-18, Step 2: Simulation, ballot grading and optimizers

**Done:**
- `pickem/simulate.py`: runs N stages and keeps every team's record in every
  simulation (an N × 16 table). Takes about 8 s per 100k simulations.
  Has a hook for drawing team strength per simulation (not used yet).
- `pickem/ballot.py`: Valve's 2/6/2 ballot, grading, `best_expected()`
  (exact) and `best_threshold()` (P(≥5), candidate search + re-grading on
  fresh simulations).
- Explainer: [concepts/pickem-objective.md](concepts/pickem-objective.md).

**Evidence:** `tests/test_ballot.py`. Grading follows the exact-record rules
(a 3-0 doesn't satisfy an advance pick). The search's numbers equal direct
grading, and each optimizer wins on its own objective.

---

## 2026-11-18, Step 3: Event file and Baseline 0 (VRS points)

**Done:**
- `data/events/singapore-2026-stage1.json`: the 16 reported Stage 1 teams,
  seeded by the 2026-11-02 VRS global standings (the rulebook says Stage 1
  seeds follow VRS global order).
- `pickem/baseline.py`: VRS points → Elo probability (Valve's own curve,
  400 points ≈ 91%), read as a BO3 probability and converted to a BO1
  probability assuming independent maps.
- `scripts/run_stage.py`: event → probabilities → simulation → both
  ballots.

**Verification of the team list:** the list comes from a news site (win.gg).
Other outlets gave partial or conflicting lists, and Liquipedia is blocked
from this environment. Cross-check: sorting that list by VRS gives round 1
HEROIC vs Imperial and FaZe vs Wildcard, the two pairings another outlet
(insider-gaming.com) reported. **Still provisional.** The other 6 pairings
aren't confirmed yet, and Chinggis Warriors has two rosters in VRS (we used
the higher-ranked one).

**Result (Baseline 0, 100k + 100k simulations, seed 2026):**
- Very flat: seeds 1–8 are within about 75 VRS points, so the top teams each
  go 3-0 only 15–24% of the time.
- Max-expected ballot: 4.09 expected correct, **P(≥5) = 37.3%**.
  Max-P(≥5) ballot: 4.08 expected, **P(≥5) = 37.4%**. A statistical tie.
  This flat model doesn't separate the two objectives.

**Not a prediction yet.** Baseline 0 is a placeholder and the benchmark that
later models must beat. Valve's own evaluation said VRS was overconfident,
and its points aren't designed as match predictions for these specific
teams.

---

## 2026-11-18, Step 3b: Factor decisions for Model v1

The user chose from options with analysis (two rounds of questions). Full
record: [decision 0005](decisions/0005-model-v1-factors.md). In short:
own rating + VRS points (fitted blend); roster-change reset; BO1 vs BO3;
LAN weighting; event-strength weighting; region calibration; strength
uncertainty; a per-team curve against stronger/weaker opponents (the user's
idea); player ratings only after roster changes, if HLTV data is collected.
Every factor must improve predictions on held-out past matches or it's removed.

**Correction made while preparing the options:** Valve's tables show LAN
and event strength only for a roster's ten best wins and never record
BO1/BO3, so those factors are only partly supported by the data.

**Open:** the user is trying to connect a folder from their computer so their
logged-in browser can read a few HLTV pages (map pools, player ratings).

---

## 2026-11-18, Step 4: Match history from Valve's VRS snapshots

**Done:** `scripts/fetch_vrs.sh` downloads Valve's repository at a pinned
commit (`f8c55f2`, the 2026-11-02 standings). `pickem/data/vrs.py` parses
every roster page of all 48 snapshots, and `scripts/build_matches.py` writes
`data/processed/matches.csv` and `data/processed/vrs_points.csv`.
Regenerate with the two scripts; the outputs aren't committed.

**Result:** 26,631 matches, 2024-02-08 to 2026-11-01. Both lineups known
for 89%, LAN status known for 77%, event weight known for 79%.

**Problem found and fixed:** the first version matched the same match
across overlapping snapshots by team names and counted about 10,800
matches twice (37,399 rows). Valve relabels old matches when a team is
renamed ("PERA" later appears as "ex-PERA"). Now each match is taken from
the first snapshot after it was played, with a 14-day allowance for late
entries. LAN and event flags are still filled in from any snapshot. After
the fix, only 1 pair of rows shares a date and both lineups under different
names.

**Checked:** 802 cases of the same two teams meeting twice on one day. 793
come from a single snapshot with distinct Valve match IDs (genuine, e.g.
double-elimination brackets) and 297 have different winners, so they're kept.

**Known limitations:** no maps, scores, BO format or event names; team
names reflect the name shortly after each match, so a renamed team's history
is split across names (handled in the model by linking lineups).

---

## 2026-11-18, Step 5: How good are Valve's VRS points as predictions?

**Done:** `pickem/evaluate.py` (log loss, Brier, accuracy, calibration; VRS
points looked up from the snapshot strictly before each match, by lineup
first, then by name) and `scripts/eval_baseline.py`. The scale is fitted on
matches before 2025-11-01, and results are reported on matches from
2025-11-01 on, which played no part in the fitting.

**Result (test period, both teams in the global top 50, 1,440 matches):**

| Model | Log loss | Brier | Accuracy |
|---|---|---|---|
| Coin flip | 0.6931 | 0.2500 | 50% |
| VRS points, Valve's scale 400 | 0.7258 | 0.2538 | 59.5% |
| VRS points, fitted scale 1100 | **0.6648** | **0.2362** | 59.5% |

- With Valve's own curve, VRS is **worse than a coin flip** in log loss: badly
  overconfident. When it gives the favourite 92%, the favourite wins 69%.
  This confirms Valve's 2023 remark that the slope is too steep.
- One fitted number (scale 1100) fixes the calibration (predicted ≈
  observed in every bin with enough matches).
- Top-50 CS is close to random: the favourite wins only about 60%.
  **The 0.6648 log loss is the benchmark Model v1 must beat.**

**Effect on Singapore Stage 1:** `run_stage.py` now defaults to scale 1100.
The best ballot's P(≥5) falls from 37% (overconfident scale) to about 17.5%.
Treat 17.5% as pessimistic: the fitted curve mixes BO1 and BO3 results (the
data doesn't record format), and the simulator then makes BO1s even flatter,
so BO1 randomness is probably counted twice. Model v1's BO1/BO3 check
addresses this.

---

## Open questions for the user (answer whenever you review)

1. Confirm the Stage 1 team list and round 1 pairings from the official
   bracket or in-game Pick'Em once they're published.
2. ~~Factor discussion~~ Done: decision 0005.
3. Are you OK with the network policy as is (no Liquipedia)? Or should we add
   it for brackets and rosters, accepting its API terms?

## Next steps (proposed)

- **Step 6:** Model v1 with the factors in decision 0005, each tested
  against the 0.6648 benchmark on the same held-out matches; BO1/BO3 check
  on past Major Swiss matches.
- **Step 7:** strength-uncertainty sampler; backtest ballots on past Majors.
- **Later:** map/veto model (needs map-level data), Stages 2–3 and playoffs,
  a web page.
