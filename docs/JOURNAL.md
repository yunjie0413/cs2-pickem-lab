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

**Caveats:** the bracket was still unconfirmed when this ran; it has since
been confirmed with no changes to the result (Step 6d). The simulator
treats every win probability as exact (strength uncertainty is Step 7), so
31.5% is probably a little optimistic.

---

## 2026-11-18, Step 6d: Stage 1 bracket confirmed

**Why only now:** the event file (Step 3) was built from news reports while
the cloud session couldn't reach Liquipedia. After the move to the PC (Step
5b) this check should have come first; it was put behind the model work. The
model itself doesn't depend on the team list, only the ballot does.

**Checked** (2026-11-18): Liquipedia (seeds, format, round 1, 9z's roster),
Wikipedia (rosters, round 1, team names), HLTV match pages (round 1).
- All 16 teams and seeds 1–16 match the event file; seeds follow the
  2026-11-02 VRS standings.
- All 8 round 1 pairings match (seed 1v9 … 8v16), all Bo1 on 2026-11-24;
  the first match starts at 12:00 Singapore time (UTC+8).
- The format matches the simulator: Bo3 for advancement and elimination
  matches, Bo1 otherwise; later rounds paired by Buchholz, then seed.
- PARIVISION plays as **PVISION** and BC.Game as **GOSH** (Singapore doesn't
  allow gambling brands). The event file now uses these names so the ballot
  reads like the in-game Pick'Em; the model finds both teams by lineup.
- **9z benched meyern on 2026-11-07; history stands in.** The model still
  finds 9z through the other four players but can't yet tell whether the
  stand-in is weaker. That is one job of the player-ratings step.

**Result:** every probability and both ballots are unchanged (Step 6c).

---

## 2026-11-18, Step 7a: HLTV player ratings for roster changes

**Order agreed with the user:** player ratings → Step 7 → map model.

**Data:** HLTV's player statistics table, one page per calendar month from
2024-02 to 2026-11 (up to 11-17), each read twice: against all opponents,
and against top-50 opponents only (HLTV's ranking at the time of the
match). 68 pages, read in the user's Chrome one page every 8–15 seconds,
no errors, the same columns on every page: 65,516 rows (285 to 1,877 per
page). Saved as one CSV with the user's OK and moved to
`data/raw/hltv/players_monthly.csv` (gitignored). HLTV shows Rating 3.0
for every month, so the whole series uses one scale.

**Name matching:** Valve's lineups give nicknames only. They are matched to
HLTV players by lowercase name; when two HLTV players share a name, the one
who played for a team of the same name wins, then the one with more rounds.
99.7% of player appearances for VRS top-100 teams in training + validation
find an HLTV player (1,047 of 1,053 players; the 6 misses are minor
players).

**How often lineups change** (Valve's data, training + validation): in 10%
of team appearances (2,067 changes). 1,608 of them change one player, 403
two, 56 three or more; 521 go straight back to the lineup before (a one-off
stand-in).

**Method, as first fixed before any result** (`pickem/data/hltv_players.py`):
- A player's value on a date uses only the 6 calendar months before that
  date's month.
- The value is the rating against top-50 opponents, because ratings
  against weak opponents are inflated, pulled toward a prior (500 rounds,
  about 25 maps, weigh as much as the prior). Players with few such rounds
  were to be filled in from the rating against all opponents, translated by
  a straight line fitted on player-months with at least 300 rounds of both
  (training months only).
- **Factor `roster_skill`:** when a team's lineup changes, its rating moves
  by β × (summed value of the players who joined − summed value of those
  who left). A stand-in counts when he comes in and is reversed when the
  regular player returns. New teams still start at the average (decision
  0005: player ratings only after roster changes). The same adjustment is
  applied at prediction time when an event roster differs from the team's
  last lineup (9z's stand-in).
- Tested like every other factor: β tuned on the training period, kept only
  if it helps on all validation matches by more than 2 standard errors.

**The first rule failed a data check, before the factor test was run.**
The fitted line was top-50 rating = 0.001 + 0.980 × all-opponent rating,
almost no change: for players with plenty of both kinds of rounds, most of
their "all" rounds *are* top-50 rounds, so the line can't show the
inflation. Result: 9z's stand-in history (735 rounds in May–October 2026,
none against top-50 teams, rating 1.23) got a value of 1.12, about frozen's
or Twistzz's level. Two measurements on training months, from the player
file only (no match results), replaced the rule:
1. Players who faced both kinds of opponents in the same 6 months rated
   **+0.088** higher against non-top-50 teams (4,619 player-windows), and
   about the same gap at every mix (+0.086 to +0.094 whether 0–20% or
   60–80% of their rounds were against top-50 teams).
2. 115 players moved up: a 6-month window with under 100 top-50 rounds and
   at least 300 others, then at least 200 top-50 rounds in the next 6
   months. Their later top-50 rating averaged **0.96** whatever they had
   shown before (correlation with their earlier rating 0.14; the 12 who had
   been above 1.2 ended at 0.93). This is the stand-in / new-signing case.

New rule: value = (0.96 × 500 + top-50 rating × top-50 rounds + w × other
rounds × (other rating − 0.088)) / (500 + top-50 rounds + w × other rounds),
with the weight w and the prior 0.96 fitted on the 115 players by least
squares. **w came out 0.00**: the fit is flat from 0 to 0.10 (error 0.1262
to 0.1266) and worse above, and even the best version barely beats a
constant (error 0.126 against a spread of 0.128). In effect a player's
value is his rating against top-50 opponents pulled toward 0.96, and
ratings against weaker opponents are not used. history's value is now
0.960 (meyern's 0.940).

**Which matches count as "just after a lineup change"** (printed for
information only): first planned as within 60 days of a change, but that
covered 87% of validation matches because lineups change so often, so it is
within 5 matches of a change instead.

**Factor test, one-at-a-time rule as written** (each factor switched off
from the all-factors model, the rest re-tuned on training; gain on all
1,694 validation matches):

| Factor | Gain, player ratings in the model | Step 6 (no player ratings) |
|---|---|---|
| time decay | −0.0008 ± 0.0010 | +0.0039 ± 0.0013, kept |
| roster reset | −0.0018 ± 0.0011 | +0.0023 ± 0.0015 |
| region | +0.0019 ± 0.0009, kept | +0.0054 ± 0.0014, kept |
| volatility | −0.0009 ± 0.0013 | −0.0022 ± 0.0015 |
| player ratings (β) | +0.0023 ± 0.0018 | not available |

All factors in: validation log loss 0.6587 (Step 6: 0.6619). β tuned to
800 rating points per unit of player value (1,600 was tried and was
worse); on matches within 5 matches of a lineup change (764) its gain is
+0.0022 ± 0.0033.

**Problem with the rule, not with the data:** time decay (learn faster
after a break) and player ratings both handle "this team just changed", so
each looks useless while the other is in the model, and testing one at a
time dropped both, leaving region only. This is a known weakness of
one-at-a-time tests when two factors overlap. Which selection rule decides
is the user's call; asked before running any alternative, so the choice
can't follow from which factors it keeps.

**User's choice: backward elimination** (decision 0007). Implemented in
`scripts/fit_model_v1.py` step [2].

**Result (2026-11-19): no factor survives.** Gains in standard errors, each
round re-tuned without the factor removed in the round before:

| Round | time decay | roster reset | region | volatility | player ratings | removed |
|---|---|---|---|---|---|---|
| 1 | −2.1 | −1.7 | +2.2 | −0.7 | +0.6 | time decay |
| 2 | | −1.0 | **+3.5** | +1.0 | **+2.5** | roster reset |
| 3 | | | +1.9 | +0.1 | +1.1 | volatility |
| 4 | | | +1.6 | | +0.6 | player ratings |
| 5 | | | +1.7 | | | region |

Region on cross-region matches alone: +0.006 ± 0.004 in every round. The
no-factor model scores 0.6547 on the top-50 validation matches, the same as
Step 6's model (time decay + region, 0.6547); region alone scored 0.6526.

**Why this result is not trustworthy as it stands: tuning noise.** The
same test (time decay removed from the full model) gave −0.0008 in the
first run and −0.0020 here, only because the unused LAN weight was held
fixed instead of free, so the coordinate search ended elsewhere. Each
comparison model gets one quick tuning pass, so the models being compared
are noisy by about ±0.001–0.002, the size of the effects tested. Round 2→3
shows it: removing roster reset (a factor that hurt) cut region from +3.5
to +1.9 SE and player ratings from +2.5 to +1.1.

**Stage 1 with the no-factor model** (advance %, Step 6c in brackets):
FlyQuest 44.6 (31.6), Lynn Vision 41.5 (32.5), Chinggis 21.3 (12.6), GOSH
20.0 (27.7), PVISION 67.6 (74.6), HEROIC 64.9 (72.9). Best ballot: P(≥5) =
24.9% (31.5%); Liquid → M80 in the advance picks. Most of the change is
losing region calibration (teams from weaker regions keep inflated
ratings).

**User's choice: tune fully, same rule** (decision 0007, amendment). Every
tuning now repeats its coordinate passes until a whole pass finds nothing
better (at most 10).

**Re-run with full tuning: still no factor, and my diagnosis above was
wrong.** From round 3 on the numbers are identical to the first run, so
one-pass tuning was not what made the gains swing:

| Round | time decay | roster reset | LAN | region | volatility | player ratings | removed |
|---|---|---|---|---|---|---|---|
| 1 | −0.7 | +1.7 | −2.7 | +3.4 | −1.1 | +1.0 | LAN |
| 2 | −0.7 | +3.3 | | +2.6 | +0.3 | +1.0 | time decay |
| 3 | | −1.0 | | +3.5 | +1.4 | +2.5 | roster reset |
| 4 | | | | +1.9 | +0.1 | +1.1 | volatility |
| 5 | | | | +1.6 | | +0.6 | player ratings |
| 6 | | | | +1.7 | | | region |

The swings come from the factors changing each other's value: removing LAN
moved roster reset from +1.7 to +3.3 SE, removing time decay then flipped it
to −1.0, removing roster reset then cut region from +3.5 to +1.9. Time
decay, roster reset and player ratings all change how fast a rating moves
after a team changes, so what one adds depends on which others are there.
With effects of 0.002–0.005 and standard errors of 0.001–0.002, 1,694
validation matches can't prove any single one of them. The no-factor model
is not shown to be better either; nothing is shown to help clearly.

**Model v1 is now our own rating + the VRS blend** (k = 32, 16× faster
learning for new teams, blend own 0.581 / VRS 0.093, fitted on training +
validation; BO3 scale 1.11, BO1 from BO3 by independent maps, refitted by
the user's run of `check_bo_format.py`). Stage 1 is as in the table above
(the user's run used the same model). The test period is still unscored.

**Open risk for the picks:** without region calibration, teams that mostly
play in weaker regions (FlyQuest, Lynn Vision, Chinggis Warriors) keep
ratings inflated by home results; on cross-region matches region helped by
+0.006 ± 0.004 to ± 0.006 in every round, below the bar but always
positive. Step 7's strength uncertainty will widen exactly these teams'
outcomes; whether to revisit region is the user's call.

---

## 2026-11-19, Step 7b: strength uncertainty in the simulator

**User's choice:** Step 7 now (over revisiting region or the map model).

**Idea.** A team's true strength at an event differs from our estimate,
and the difference lasts the whole event, so its results there are linked:
an underrated team tends to win several matches. Simulating every match
with fixed probabilities treats the errors as independent.

**Simulator** (`pickem/uncertainty.py`): each simulated stage draws one
offset per team, e ~ N(0, σ²) in blend-logit units, and plays the whole
stage with BO3 = sigmoid(s × (κ × logit + e_i − e_j)), BO1 from BO3 by
independent maps. κ = √(1 + π s² σ² / 4) undoes the flattening that
averaging over the offsets would cause, so a single match's probability,
averaged over the draws, stays what the model was calibrated to (checked:
within 0.008 for Stage 1 at σ = 0.35); only the links between matches
change. Tests: `tests/test_uncertainty.py`.

**Measuring σ** (`scripts/fit_uncertainty.py`): 960 HLTV-linked LAN
matches in 62 events (training + validation; the test period untouched).
Each team's rating is frozen at its first match of an event, as in the
simulator; if teams are mis-rated, their residuals at the same event lean
the same way, E[r_k r_l] ≈ g_k g_l σ² (weighted least squares on the
products, 3,114 pairs).
- Result: σ² = −0.017 (below zero, so σ = 0); split by period, both 0.
  Only teams with fewer than 60 matches show a spread (σ = 0.85 ± 0.45,
  121 pairs); every Stage 1 team has played 93 or more.
- **Can the method find a spread that is there?** These same matches
  simulated with a known σ: true 0.1 → estimated σ² 0.024 ± 0.070, 0.2 →
  0.059 ± 0.083, 0.3 → 0.098 ± 0.089, 0.5 → 0.220 ± 0.102. The method is
  about right but noisy: 960 matches only rule out σ above about 0.35
  (about 105 rating points); 0 and 0.3 can't be told apart.
- For comparison, theory for a rating updated by 32 points per match puts
  its error at about 0.15–0.2 in these units.

**Does it matter for the picks? No.** Stage 1, best ballot for P(≥5):

| σ | ballot | P(≥5) |
|---|---|---|
| 0 (measured) | 3-0 PVISION, 100 Thieves · advance NiP, HEROIC, FaZe, Eternal Fire, 9z, M80 · 0-3 GOSH, Chinggis | 24.9% |
| 0.2 (theory) | same | 24.8% |
| 0.35 (upper end) | same | 24.4% |

Every team's advance chance moves by under 1.5 points. The simulator uses
the measured σ (0) by default; `run_stage.py --sigma X` sets it by hand.

**Still open in Step 7:** backtesting whole ballots on past Majors (needs
their brackets and results; a handful of stages has little power, so it
can catch gross errors only).

---

## 2026-11-19, Step 8: map model

**User's choice:** the map model next (over the past-Major backtest,
revisiting region, or finalizing).

**Data:** the LAN map results already collected (Step 6a): 5,666 maps in
2,450 series between HLTV top-50 teams, 2024-12-01 to 2026-11-17. Thin per
team: over the last 12 months most Stage 1 teams have 5–40 LAN maps on each
map, Chinggis Warriors none; Cache entered the pool only in 2026-Q3.

**Plan, fixed before any result:**
1. *Gatekeeper, map level, with the map played known.* For each map, the
   current model's map win probability p0 (series probability → map
   probability by independent maps) is adjusted by per-team, per-map
   offsets learned online from earlier maps (`pickem/maps.py`): centred
   per team, so they only move a team between its own maps; fading with a
   half-life. Learning rate and half-life tuned on training maps
   (2024-12 to 2025-05); kept only if better than p0 on validation maps
   (2025-06 to 2025-10) by more than 2 standard errors. Test period unused.
2. Only if step 1 passes: a simple veto turning offsets into BO1/BO3
   probabilities, tested at series level, then Stage 1. If step 1 fails,
   no veto model can help and the map model stops there (and online maps,
   which the user allowed only if the map model shows a difference, are
   not collected).

**Result: step 1 fails, so the map model stops** (`scripts/fit_map_model.py`).
5,495 maps with a linked series and VRS points (training 1,031,
validation 1,208).
- Tuning on training maps: the best setting (learning rate 0.05,
  half-life 60 days) gains only +0.0004 per map; any faster learning makes
  predictions clearly worse (learning rate 0.5: −0.017 to −0.030), so the
  map signal in 5–40 maps per team is weaker than the noise.
- Validation: log loss 0.6752 without offsets, 0.6755 with; gain −0.0003 ±
  0.0007 (−0.5 SE). No effect, even with the played map known; with the
  veto unknown, as in Pick'Em, it could only be weaker.
- Caveat: the file has no veto data. Teams win their own map picks more
  often, which can't be measured here; in a BO3 each team gets one pick,
  so at series level it largely cancels.
- Online map results are not collected (the user's condition: only if the
  map model shows a difference). Stage 1 is unchanged.

## 2026-11-19, Step 7c: backtest on past Majors' Stage 1

**User's choice:** "Backtest on past Majors first", over finalizing now or
revisiting region. Question: would our ballots have reached 5 correct, and
is our predicted P(≥5) believable?

**Stages:** Perfect World Shanghai 2024 Opening Stage, BLAST.tv Austin 2025
Stage 1, StarLadder Budapest 2025 Stage 1, IEM Cologne 2026 Stage 1.

**Data** (`scripts/build_past_events.py` → `data/events/past/*.json`):
- Seeds and final records were read from Liquipedia in the user's Chrome:
  ordinary page views, about ten in all. Liquipedia refused scripted fetches
  (403), so we didn't use them.
- The seed order is the order of the stage's invite list on each event
  page. For every stage it matches all 8 round-1 pairings (seed i vs i+8).
  That check confirms the pairs, not the order within each pair. The order
  only affects later-round pairings.
- Shanghai was seeded by regional standings within each region's slots;
  the other three by global standings.
- Each team's lineup comes from its first stage match in Valve's data.
  VRS points come from the last snapshot before the stage. All 64 teams
  were found.

**Method** (`scripts/backtest_majors.py`):
- Model v1 replays only the matches before the stage started
  (`load_model(..., before=start)`). It uses the same settings, blend and
  BO3 scale as for Singapore, with σ = 0.
- Baseline 0 is VRS points at Elo scale 1100.
- For each model, 50,000 simulations choose the ballots (A = most expected
  correct picks, B = highest P(≥5), as in `run_stage.py`). A fresh 50,000
  give the predicted numbers. The ballots are then graded against the real
  records.
- Record log score: the average −ln P(the record each team actually
  finished with). Lower is better. Knowing nothing (all six records equally
  likely) scores ln 6 = 1.792.

**Leakage, stated before the run:**
- The ratings use only earlier matches. The model's settings, however,
  were tuned on 2024-08 to 2025-10, and the BO3 scale on all linked
  matches. So the settings saw Shanghai's year (training) and Austin
  (validation).
- Budapest and Cologne are in the **test period**. This backtest looks at
  their results before the single `--final` scoring, so **no model change
  may be based on them**. Their roughly 66 stage matches are a small part
  of the test period, so the final score loses little of its blindness.

**Results:**

| Stage | P(≥5) v1 ballot B | v1 correct, A / B | P(≥5) baseline | baseline correct, A / B | record log score v1 / baseline |
|---|---|---|---|---|---|
| Shanghai 2024 | 29.9% | 3 / **5** | 28.6% | 3 / 3 | 1.570 / 1.620 |
| Austin 2025 | 29.9% | 4 / 4 | 22.2% | **6 / 6** | 1.678 / 1.667 |
| Budapest 2025 | 29.3% | 3 / 3 | 27.5% | **6 / 6** | 1.747 / 1.744 |
| Cologne 2026 | 24.3% | **5 / 5** | 22.8% | 2 / 1 | 1.626 / 1.652 |
| **Total** | 1.14 passes expected | 1 / 2 passes; 15 / 17 correct (14.8 expected) | 1.01 expected | 2 / 2 passes; 17 / 16 correct (14.3 expected) | 1.655 / 1.671 |

Model v1's B ballots, for reference:
- Shanghai, 5 correct: 3-0 Liquid, MongolZ | advance FURIA, VP, Complexity,
  BIG, paiN, FlyQuest | 0-3 Passion UA, Rare Atom.
- Austin, 4 correct: 3-0 Complexity, HEROIC | advance B8, TYLOO, FlyQuest,
  Imperial, Legacy, Fluxo | 0-3 Chinggis, Metizport.
- Budapest, 3 correct: 3-0 Legacy, PARIVISION | advance FaZe, B8,
  GamerLegion, Fnatic, Lynn Vision, NRG | 0-3 RED Canids, The Huns.
- Cologne, 5 correct: 3-0 GamerLegion, BetBoom | advance B8, HEROIC, BIG,
  M80, MIBR, Lynn Vision | 0-3 Gaimin, FlyQuest.

**Findings:**
1. **Calibration looks fine, as far as 4 stages can show.** We expected
   about 1.1 passes and saw 2 with each model. Expected correct picks were
   14.8 and the actual totals were 15 to 17. With about 28% per stage, 2 or
   more passes in 4 stages happens about 1 time in 3.
2. **The backtest can't separate Model v1 from Valve's points.** On record
   log score Model v1 is better by 0.016 ± 0.014 per team. The stage is
   the unit, since teams in one stage share outcomes. That is about 1 SE.
   Each model passed twice. The validation-match result (log loss 0.6547 vs
   0.6605 over 1,694 matches) remains our evidence for Model v1. 4 stages
   can neither confirm nor overturn it.
3. **Stage 1 is close to a lottery.** Both models beat knowing nothing by
   only about 0.13 nats per team. Singapore's 24.9% P(≥5) is within the
   22–30% range of these four stages.
4. **Where the models disagree** (the 5 teams per stage with the biggest
   gap in advance chance), Model v1's direction was right 10 times out of
   20. A pattern noticed only after looking:
   - When Model v1 rated an Americas or Asia team above its VRS standing,
     it was right 2 times out of 9. It was wrong on FlyQuest, Fluxo,
     Imperial, NRG, THUNDERdOWNUNDER and twice on Lynn Vision, and right on
     paiN and Legacy.
   - When it rated a European team above VRS, it was right 3 times out of 3.

   This fits the open region risk from Step 7a. But it is post hoc and
   only 9 cases (p ≈ 0.09 if each were a coin flip), and 4 of the 9 are
   test-period stages. So it is a hint, not evidence, and by the rule
   above it is not grounds for a change.
5. **A region re-test on cross-region matches would add nothing.** Region
   offsets only change predictions for matches between regions: 359 of
   the 3,734 validation matches. Both the paired test's total and its
   variance come almost entirely from those matches. A subset test would
   therefore repeat the backward-elimination verdict (region dropped).

**For Singapore:** nothing changes. The only pick that depends on region
is M80 vs Liquid for the last advance slot (Step 7a).

## 2026-11-19, Step 9: test period scored once, final Singapore picks

**User's choice:** "Finalize now", over hedging the region pick or using
Baseline 0.

**Test period, scored once** (`fit_model_v1.py --final`). The tuning is
deterministic: it repeated the earlier result, no factors kept and blend
0.581 / 0.093, and rewrote the same `model_v1.json`. Matches from
2025-11-01 onward, both teams in the VRS top 50:

| | log loss | Brier | accuracy |
|---|---|---|---|
| coin flip | 0.6931 | 0.2500 | 50.0% |
| Baseline 0 (VRS points, refitted) | 0.6648 | 0.2362 | 59.5% |
| Model v1, own rating only | 0.6536 | 0.2311 | 60.6% |
| **Model v1, own rating + VRS blend** | **0.6538** | **0.2312** | **60.8%** |

- **Model v1 beats Baseline 0 by +0.0110 ± 0.0034 per match (3.2 SE)**
  on 1,440 matches. The margin is larger than on validation (+0.0058 ±
  0.0052, 624 matches), so the selection didn't overfit validation.
- On the test period, the VRS term adds nothing beyond our own rating
  (0.6536 vs 0.6538). It is kept, because the blend was fixed before this
  score.
- Calibration is good. Favourites at 55–70% won about 1.5–2 points less
  often than predicted, and favourites above 70% won slightly more often.
- Not tested here: the BO3 scale (fitted on linked matches, test period
  included) and anything Major-specific (Step 7c).

**Inputs are current (checked today):**
- Valve's VRS repository: the local copy matches the remote head. The
  newest snapshot is 2026-11-02, and the next is expected on the first
  Monday of December, after the Major.
- Liquipedia: the event page was last edited 2026-11-14 and the Stage 1
  page 2026-11-16. Both edits predate our 2026-11-18 confirmation, so no
  roster has changed.

**Final ballot (B, highest P(≥5), per decision 0002):**

| Pick | Teams |
|---|---|
| 3-0 | **PVISION, 100 Thieves** |
| Advance (3-1 or 3-2) | **Ninjas in Pyjamas, HEROIC, FaZe, Eternal Fire, 9z, M80** |
| 0-3 | **GOSH, Chinggis Warriors** |

- P(≥5 correct) = 24.9%. Expected correct picks = 3.60, on 100,000 fresh
  simulations.
- P(exactly k correct): 1: 5%, 2: 16%, 3: 27%, 4: 26%, 5: 16%, 6: 7%,
  7: 2%.
- Ballot A (most expected correct) swaps two picks: Liquid replaces
  PVISION in 3-0, and PVISION replaces M80 in advance. It scores 24.7%.
  The two are practically tied, and B is the formal pick.

**Caveats:**
1. **About 1 chance in 4.** Even the best ballot most likely gets 3 or 4
   correct. The four past Stage 1s gave 22–30% (Step 7c).
2. **Region risk.** If teams from Americas and Asia are overrated by our
   rating (Step 7a, and the hint in Step 7c), the M80 advance pick is the
   one at risk. With the region factor, Liquid would take that slot.
3. **No matches after 2026-11-01.** Valve's data ends with the 2026-11-02
   snapshot, so the last three weeks of form are missing.
4. **9z play with a stand-in** (history in for meyern). The player-rating
   adjustment is 0 because roster_skill was dropped, so 9z's rating
   assumes their usual strength.
5. **σ = 0:** no extra spread of team strength per stage (Step 7b).

**Before the lock (2026-11-24 12:00 SGT):**
- Re-check the rosters once on 2026-11-23 or the morning of the 24th.
- If a lineup changes, update `data/events/singapore-2026-stage1.json` and
  re-run `python scripts/run_stage.py data/events/singapore-2026-stage1.json`.
- Otherwise the picks above stand.

**Superseded the same day by Step 9b**, which adds the November matches.

## 2026-11-19, Step 9b: November results from HLTV

**User's question and choice:** "Aren't all matches on HLTV?" The user
chose "Beijing + collect rest of November" over using only the Beijing
maps we already had, or keeping the picks.

**Why three weeks were missing:** the ratings run on Valve's match list,
which Valve publishes once a month with each VRS snapshot. The newest one
(2026-11-02) ends on 2026-11-01, and the next is due after the Major. Until
now HLTV served only to label matches (LAN, BO1 or BO3).

**Collection (user's Chrome, 2026-11-19):**
- HLTV's results page, filtered by team and by 2026-11-02 to 2026-11-19,
  for each of 15 Stage 1 teams. The pages were read 8–15 seconds apart, in
  about 3.5 minutes.
- GOSH has no HLTV team of that name. BC.Game's page and s1mple's
  player page show no November matches, so GOSH hasn't played.
- The rows are saved in `data/raw/hltv/results_recent.csv`, which is
  gitignored and stays on the user's PC.
- Dates come from each row's Unix timestamp. The page's day headings shift
  with the browser's time zone, so they aren't used.
- 34 rows give 27 distinct matches. Matches between two Stage 1 teams
  appear on both pages and count once. DENDELE 3-0 Imperial (1 November,
  23:22 UTC) is already in Valve's list, so it isn't counted again.

**Who played:**
- IEM Beijing (2–6 November, LAN): PARIVISION, Liquid, HEROIC, FaZe and 9z.
- PGL Cluj-Napoca 2027 closed qualifier (15–17 November): PARIVISION,
  HEROIC, FaZe, Eternal Fire and 100 Thieves.
- Stake Ranked (17–18 November): NiP.
- No matches since Valve's list: M80, DENDELE, Imperial, Wildcard, GOSH,
  FlyQuest, Chinggis Warriors and Lynn Vision.

**How the matches are used** (`pickem/data/hltv_recent.py`,
`load_model(recent_for=...)`):
- The engine processes them after Valve's list, in time order, exactly
  like Valve's matches.
- Stage 1 teams play with their event-file lineups.
- Opponents are found by name in Valve's list: HLTV names are learned from
  the linked LAN series, otherwise matched after normalising. All 27
  matches resolved; none were skipped.
- **The model itself is unchanged** (same settings); it just sees more
  matches.
- `run_stage.py` uses the file by default; `--no-recent` turns it off. The
  backtest doesn't use it.

**Effect:**

| Team | Rating before | Rating after | Advance % before | Advance % after |
|---|---|---|---|---|
| 100 Thieves | 1976 | **2025** | 57.5 | **65.8** |
| PVISION | 2044 | 2017 | 67.6 | 64.9 |
| Ninjas in Pyjamas | 2039 | 2024 | 66.4 | 65.1 |
| HEROIC | 2028 | 2014 | 64.9 | 64.0 |
| FaZe | 2006 | 1961 | 62.1 | 56.5 |
| Eternal Fire | 1993 | 1960 | 58.6 | 54.4 |
| Liquid | 1951 | 1957 | 55.3 | 57.2 |
| 9z | 2006 | **1956** | 59.0 | **52.9** |
| M80 (no new matches) | 1976 | 1976 | 53.0 | 54.4 |

What drove the changes:
- 100 Thieves beat Eternal Fire, PARIVISION and fnatic in the qualifier.
- 9z lost both Beijing series, to BetBoom and TYLOO.
- FaZe won 0 of 4 series, the last two to fnatic and HEROIC.

**New final ballot** (the two objectives now pick the same ballot):

| Pick | Teams |
|---|---|
| 3-0 | **Liquid, 100 Thieves** |
| Advance (3-1 or 3-2) | **Ninjas in Pyjamas, PVISION, HEROIC, FaZe, Eternal Fire, M80** |
| 0-3 | **GOSH, Chinggis Warriors** |

- P(≥5 correct) = 24.7%. Expected correct picks = 3.56.
- Changes from Step 9: 9z is out. PVISION moves from 3-0 to advance, and
  Liquid takes its 3-0 slot.

**Caveats added:**
- The qualifier and Stake Ranked matches were most likely played online.
  A week before a Major, teams may hold back strategies or field
  stand-ins.
- Opponents' lineups are unknown; they are matched by name.
- Region and the other Step 9 caveats still apply.

**Before the lock:** along with the roster check on 2026-11-23, the
November results can be collected again for matches played since 19
November. That would be a new collection round and needs the user's OK.
Then re-run `run_stage.py`.

---

## Open questions for the user (answer whenever you review)

1. ~~Confirm the Stage 1 bracket~~ Done: Step 6d.
2. ~~Factor discussion~~ Done: decision 0005, amended by 0006.
3. ~~Network policy / Liquipedia~~ No longer relevant: the project now runs
   on the user's PC, where Liquipedia is reachable.

## Next steps (proposed)

- **Agreed order (user, 2026-11-18):** player ratings from HLTV (roster
  changes, 9z's stand-in) → Step 7 → map model from the LAN maps we already
  have; online map results only if the map model shows a real gain.
- ~~**Step 7:** strength uncertainty and a backtest on past Majors~~ Done:
  Steps 7b and 7c.
- ~~**Finalize**~~ Done: Step 9. Remaining: one roster re-check before the
  lock (2026-11-24 12:00 SGT), and a re-run only if a lineup changes.
- **Stage 2:** once Stage 1 ends, a new event file with the 8 qualifiers
  plus the Stage 2 invites, and the same pipeline.
- **Model v2 ideas from Step 6:** a proper Glicko-style uncertainty (the
  new-team boost and forgetting after breaks were the strongest settings);
  re-test roster resets as more data arrives (they leaned positive); event
  strength from HLTV event names; map pools and player ratings from HLTV.
- **Later:** Stages 2–3 and playoffs, a web page.
