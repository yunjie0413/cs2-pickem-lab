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

**Done:** `scripts/fetch_vrs.py` (originally a bash script, see Step 5b) downloads Valve's repository at a pinned
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

## 2026-11-18, Step 5b: Moved to the user's Windows PC

**Why:** a local session can use the user's own Chrome (logged into HLTV)
and isn't blocked from sites like Liquipedia. The cloud session was moved
over with `claude --teleport`; all work had already been pushed.

**Fixes needed for Windows:**
- Every file read/write now names UTF-8 explicitly. Windows on a Chinese
  system defaults to GBK, which would garble or crash on player names.
- `scripts/fetch_vrs.sh` (bash) replaced by `scripts/fetch_vrs.py`, which
  also enables long paths for Git on Windows.

**Check:** on the PC, the rebuilt match list (26,631 matches), all 31 tests
and the Step 5 evaluation (log loss 0.6648) match the cloud results exactly.

**User decision:** collect HLTV data for the current Stage 1 teams *and* for
past Majors, so map and player factors can be tested on past events like
everything else (accepting more pages and more terms-of-service risk on the
user's account). Plan in Step 6a.

---

## 2026-11-18, Step 6: Model v1, tested factor by factor

**Built:**
- `pickem/model_v1.py`: our own Elo-style rating. It goes through all 26,631
  matches in date order and predicts each one *before* learning from it, so
  every prediction uses only earlier results. Teams are followed by lineup
  (3+ of the five players in a team's latest lineup = the same team;
  otherwise the team that currently uses the name), so renames don't break a
  team's history. Each factor from decision 0005 can be switched off.
- `pickem/history.py`: everything the engine reads (Valve's matches, plus
  LAN status from HLTV, Step 6a).
- `scripts/fit_model_v1.py`: the training period (2024-08-06 to 2025-05-31)
  tunes the parameters; the validation period (2025-06-01 to 2025-10-31)
  decides which factors stay; the test period (2025-11-01 on) is scored at
  the end with `--final`.
- On top of the rating, a small logistic model blends our rating gap with
  Valve's points gap (two weights, fitted on train + validation), as 0005
  planned.

**How a factor is tested** (decision 0006): switch it off, re-tune the rest on
the training period, then compare the two versions match by match on the
validation period. Keep it only if it helps by more than 2 standard errors.

**Results** (validation: 1,694 matches between VRS top-100 teams; gain = log
loss without the factor minus with it, so positive = the factor helps):

| Factor (decision 0005) | Gain | Verdict |
|---|---|---|
| Region calibration | +0.0054 ± 0.0014 (cross-region matches only: +0.0091 ± 0.0051) | **kept** |
| Time decay | +0.0039 ± 0.0013 | **kept**, as "learn faster after a break" (below) |
| Roster-change reset | +0.0023 ± 0.0015 | dropped for now: leans positive, not clear (1.5 standard errors) |
| LAN weighting (LAN list from HLTV) | tuning kept the weight at 1.0 | dropped: no effect |
| Per-team curve vs opponent strength (one slope per team) | −0.0022 ± 0.0015 | dropped: no effect |
| Event-strength weighting | no leak-free data | on hold (decision 0006) |
| BO1 vs BO3 | Step 6b | used in the simulator |
| Strength uncertainty | belongs to the simulator | Step 7 |
| Player ratings after roster changes | not started | later |

Time decay won in its "uncertainty" form, not the classic one. After a break
the team's match count fades (time scale 240 days), so its next results move
its rating more. Pulling the rating itself toward the average was not chosen
by the tuning: after a break we don't know whether a team got better or
worse, only that we know less. (This is the idea behind Glicko's rating
deviation.)

The setting that matters most is not on the list: a team with few matches
gets a much bigger update size (32× at first, fading over about 10
matches). Valve's data starts in February 2024, so early on every team is
"new", and the boost lets ratings settle quickly.

Roster resets lean positive but aren't clear yet. Part of their job is
already done by following teams by lineup: a team that replaces 3+ players
starts fresh unless it keeps its name.

**Test period** (from 2025-11-01, both teams VRS top 50, 1,440 matches):

| Model | Log loss | Brier | Accuracy |
|---|---|---|---|
| Coin flip | 0.6931 | 0.2500 | 50.0% |
| Baseline 0: VRS points, fitted scale | 0.6648 | 0.2362 | 59.5% |
| Model v1: own rating only | 0.6538 | 0.2313 | 60.8% |
| Model v1: own rating + VRS blend | **0.6537** | **0.2312** | 60.3% |

- Better than Valve's points by **+0.0111 ± 0.0036** per match, about 3
  standard errors: a clear improvement, though not a big one in absolute
  terms (top-50 CS stays close to random; the favourite still wins only
  about 60%). Validation points the same way (+0.0058 ± 0.0061).
- The blend leans almost entirely on our rating (weights 0.56 vs 0.06 in the
  same units): once region and breaks are handled, Valve's points add little.
- Calibration stays good: predicted and observed win rates agree within
  noise in every bin with enough matches.
- Final parameters (tuned on train + validation): update size 24, new-team
  boost 32×, match count fading over 240 days, region learning rate 8.

**Problems found and fixed on the way.** Each changed the results. All were
found from validation results or by inspection, not from test scores.
1. *Leak in Valve's LAN flag* (decision 0006). The first fit "kept" LAN
   weighting with the biggest gain of any factor and with backwards weights
   (LAN wins counted least). The flag depends on results after the match.
2. *Region judged on the wrong set.* For one run I judged region on
   cross-region matches only (too few to decide anything); reverted to
   0005's rule of all validation matches.
3. *Renamed teams lost their history.* The engine kept each team under its
   first name. Found because the Stage 1 output showed HEROIC "as Sangal". A
   renamed team that later replaced 3+ players was split in two, and its
   region was looked up under the old name.
4. *Decay pulled toward the wrong average.* Time decay and roster resets
   pulled toward a fixed 1500 while new teams started elsewhere (500 in one
   fit), so ratings "decayed" upward and both factors had been judged on a
   broken version. The engine now tracks the real average of all teams; new
   teams start there and resets pull there.
5. *The parameter search stopped at range edges or drifted.* Ranges now
   extend while the best value is on an edge, and each step must improve log
   loss by at least 0.00002.
6. *Two rosters shared one rating.* A lineup was matched to the team that 3+
   of its players had *last played for*, even if that team had replaced
   them since. Former players of one team (Permitta) ended up on two teams,
   Walczaki and the current Eternal Fire, and both claimed it, so their
   results were mixed into one rating. Found because Eternal Fire's rating
   didn't fit its record (48–22 since May). Now a lineup continues a team
   only if 3+ of its players are in that team's *latest* lineup, and a name
   only continues the team that still uses it. This fix made the time-decay
   factor useful (before, a break was hidden by the other roster's matches)
   and improved the whole model on validation (0.6636 → 0.6619 with all
   factors on).

**Honesty note on the test period:** it was also scored for the two leaky
versions (void), for a version between fixes 2 and 3 (+0.0086 ± 0.0040) and
for one between fixes 4 and 6 (+0.0066 ± 0.0041); one more run after fix 3
was discarded unread. The table above is from the final model. Every change
came from validation results or from bugs found by inspecting output; none
was made because of a test score. Still, the test period has now been
looked at several times, so treat it as slightly less clean than a first
look.

---

## 2026-11-18, Step 6a: HLTV map results, collected in the user's browser

**What:** HLTV's map results list with the filters "LAN" and "ranking: top
50", 2024-12-01 to 2026-11-17: 5,666 maps from 114 pages.

**How:** a small script in the user's logged-in Chrome tab read one page every
8–15 seconds (about 22 minutes in all). It would have stopped at the first
empty page; none came. The rows were saved as a CSV and moved to
`data/raw/hltv/maps_lan_top50.csv`. That folder is gitignored, so HLTV's data
stays on the user's PC. The browser's temporary copy was deleted afterwards.

**Processing** (`pickem/data/hltv.py`):
- Maps into series: same event, same two teams, maps at most a day apart.
  Result: 2,450 series, 304 BO1, 2,090 BO3 and 56 BO5 (one 1–1 pair dropped:
  no winner).
- Series linked to Valve's match list: same winner and loser, date within a
  day. Short names such as "NIP" are learned automatically from meetings
  where the other team's name matches. 2,392 of 2,450 series are linked
  (97.6%).

**Leak check:** the ranking filter uses each team's ranking at the time of
the match, not today's: 117 different teams appear, some only in early
months (e.g. Cloud9 in December 2024). So it can't leak the future the way
Valve's flags did (decision 0006).

**Used for:** LAN status (Step 6) and match format (Step 6b). Map pools and
player ratings are not collected yet.

---

## 2026-11-18, Step 6b: BO1 vs BO3

**Question:** Valve's data doesn't record match format, and Step 5 worried
that BO1 randomness was being counted twice. HLTV's map counts give the
format of every linked match (1 map = BO1, 2–3 maps = BO3).

**Data:** linked LAN matches after a 6-month warm-up, with VRS points for both
teams: 300 BO1, 2,023 BO3 (`scripts/check_bo_format.py`).

**Result** (calibration scale: the model's probability is sigmoid(scale ×
blend); 1.0 = the fit on all matches, all formats, mostly online):
- BO1 0.66 ± 0.18, BO3 1.15 ± 0.08: BO1s are clearly more random. BO3s
  between top teams on LAN are a bit *more* predictable than the average
  match.
- The independent-maps rule fits: a team that wins a BO3 with probability q
  wins a map with p where p²(3 − 2p) = q, and a BO1 with p. On the 300 real
  BO1s this does as well as their own fitted scale (log loss 0.6684 vs
  0.6681). Example: a 60% BO3 favourite wins about 56–57% of BO1s.

**Decision:** BO3 = sigmoid(1.15 × blend); BO1 is derived from the BO3
probability by independent maps (more precise than a scale fitted on only
300 BO1s). This replaces the Step 5 workaround: each format is now
calibrated against real matches of that format.

---

## 2026-11-18, Step 6c: Singapore Stage 1 with Model v1

**Team check:** all 16 teams are found by lineup under their current names,
and every team's chain of credited matches was listed (names used, players
shared with today's roster). Six have played with mostly today's players
since 2024: 9z, M80, DENDELE (the former Sharks), Imperial, FlyQuest and
Lynn Vision. 100 Thieves is new (February 2026, all 93 matches with today's
core). The rest formed their current core more recently:

| Team | Today's core (3+ of the 5) together since | Matches with today's core |
|---|---|---|
| BC.Game | 2026-07-31 | 30 |
| Eternal Fire | 2026-04-23 | 75 |
| Ninjas in Pyjamas | 2026-04-23 | 63 |
| Wildcard | 2026-03-23 | 58 |
| Liquid | 2026-03-19 | 55 |
| PARIVISION | 2026-01-16 | 69 |
| HEROIC | 2026-01-14 | 87 |
| Chinggis Warriors | 2025-10-23 | 78 |
| FaZe | 2025-10-04 | 91 |

Because roster resets didn't pass the test, a rating carries over a roster
change and then adapts. With update size 24, results from 30 matches ago
still carry roughly a third of their weight, from 60 matches ago about an
eighth. So only BC.Game leans noticeably on an earlier roster (its chain
includes the BLEED lineup and an earlier BC.Game lineup, 158 matches with
none of today's players). That matters because BC.Game is a 0-3 pick (see
below).

**Chance to advance** (100,000 simulated stages):

| Seed | Team | Advance | | Seed | Team | Advance |
|---|---|---|---|---|---|---|
| 1 | Ninjas in Pyjamas | 71% | | 9 | M80 | 49% |
| 2 | PARIVISION | 75% | | 10 | DENDELE | 39% |
| 3 | HEROIC | 73% | | 11 | Imperial | 35% |
| 4 | FaZe | 70% | | 12 | Wildcard | 40% |
| 5 | Liquid | 61% | | 13 | BC.Game | 28% |
| 6 | Eternal Fire | 62% | | 14 | FlyQuest | 32% |
| 7 | 100 Thieves | 66% | | 15 | Chinggis Warriors | 13% |
| 8 | 9z | 57% | | 16 | Lynn Vision | 33% |

**Best ballot for P(≥5)** (graded on fresh simulations):
- 3-0: PARIVISION, 100 Thieves
- Advance: Ninjas in Pyjamas, HEROIC, FaZe, Liquid, Eternal Fire, 9z
- 0-3: BC.Game, Chinggis Warriors
- P(≥5 correct) = 31.5%, expected correct 3.85. The ballot that maximises
  expected correct picks puts HEROIC in 3-0 instead of 100 Thieves and gets
  31.1%.
- Close calls: the second 0-3 pick is nearly a tie (0-3 chance: BC.Game
  21.6%, Lynn Vision 20.2%, FlyQuest 19.6%), and BC.Game's rating is the
  least settled (above). The sixth advance pick is clearer (9z 56.5%, next
  M80 48.9%).

**Why higher than Baseline 0 (17.5%):** Model v1 separates the teams more (it
predicts better, and its calibration says the gaps are real), and BO1s are no
longer flattened twice.

**Caveats:** the team list and seeding are still provisional. The simulator
treats every win probability as exact (strength uncertainty is Step 7), so
31.5% is probably a little optimistic.

---

## Open questions for the user (answer whenever you review)

1. Confirm the Stage 1 team list and round 1 pairings from the official
   bracket or in-game Pick'Em once they're published (Stage 1 is reported
   to start 2026-11-24).
2. ~~Factor discussion~~ Done: decision 0005, amended by 0006.
3. ~~Network policy / Liquipedia~~ No longer relevant: the project now runs
   on the user's PC, where Liquipedia is reachable.

## Next steps (proposed)

- **Before picks lock:** confirm teams, seeds and round 1 pairings; update
  the event file; re-run.
- **Step 7:** strength uncertainty in the simulator (each simulated stage
  draws team strengths from how well we know each team: fewer matches with
  today's core, or a long break, means a wider spread), and a backtest of
  whole ballots on past Majors' Stage 1 (Austin 2025, Budapest 2025, Cologne
  2026): would our ballots have reached 5, and is our P(≥5) calibrated?
- **Model v2 ideas from Step 6:** a proper Glicko-style uncertainty (the
  new-team boost and forgetting after breaks were the strongest settings);
  re-test roster resets as more data arrives (they leaned positive); event
  strength from HLTV event names; map pools and player ratings from HLTV.
- **Later:** Stages 2–3 and playoffs, a web page.
