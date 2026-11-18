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

## Open questions for the user (answer whenever you review)

1. Confirm the Stage 1 team list and round 1 pairings from the official
   bracket or in-game Pick'Em once they're published.
2. Factor discussion: which factors do you want in Model v1? (Starting
   proposal is in the project's chat history; to be recorded here as
   decision 0005.)
3. Are you OK with the network policy as is (no Liquipedia)? Or should we add
   it for brackets and rosters, accepting its API terms?

## Next steps (proposed)

- **Step 4:** parse the VRS per-roster match tables into one deduplicated
  match history (one row per match ID).
- **Step 5:** measure Baseline 0 on past matches (calibration, log loss) and
  fit its scale parameter. This includes past Major Swiss matches.
- **Step 6:** factor discussion → Model v1 (own rating with time decay, roster
  continuity, LAN weighting), compared against Baseline 0 on the same
  held-out matches.
- **Step 7:** strength-uncertainty sampler; backtest ballots on past Majors.
- **Later:** map/veto model (needs map-level data), Stages 2–3 and playoffs,
  a web page.
