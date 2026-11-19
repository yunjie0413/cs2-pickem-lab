# 0006: Valve's LAN flags and event weights are not used; how factors are tested

Date: 2026-11-18. Status: accepted (a correctness fix found while testing;
the factor choices of decision 0005 stand, only their data and test change).
Amends the "LAN weighting" and "event-strength weighting" rows of 0005.

## What happened
The first Model v1 fit kept "LAN weighting" with the largest gain of any
factor (+0.0096 ± 0.0032 on validation), and the model then beat Valve's
points on the test period by +0.0088 ± 0.0042 per match. But the fitted
weights were backwards: LAN wins counted 0.6, online wins 1.0, and matches
with no flag 2.0.

## Why: the flag depends on results after the match
Valve's tables show LAN/online (and the event weight) only on a team's "ten
best" wins in a snapshot's 6-month window, and our match history fills a
missing flag from any snapshot. Whether a win is among a team's ten best
depends on its *other* wins, including wins after this match: a team that
goes on to win bigger matches pushes this win out of the list. So "no flag"
partly means "this team went on to win bigger matches".

Check: in every rank group, the winners of matches with no flag gained 20 to
37 more VRS points over the next 120 days than the winners of flagged
matches (for example ranks 31–60: +68 vs +42). Giving those matches double
weight let the backtest peek at the future. At the real event there is no
future to peek at, so that gain was fake. Without the flags, Model v1's
validation gain over Valve's points fell to +0.0013 ± 0.0049 (no clear
effect).

## Decision
1. Valve's LAN flags and event weights are not used anywhere in the model.
2. LAN status comes from HLTV's list of LAN maps instead (filter "top 50",
   ranking at the time of the match), linked to 2,392 of Valve's matches from
   2024-12 on. Whether a match appears there doesn't depend on who won.
3. Event-strength weighting is dropped for now: Valve's event weight has the
   same problem and there is no clean source yet. A later option: HLTV event
   names exist for LAN matches, so an event could be rated by the average
   pre-event rating of its teams.
4. How every factor is tested: switch it off, re-tune the other parameters
   on the training period, then compare the two models match by match on the
   validation period (average log loss difference and its standard error).
   Keep the factor only if it helps by more than 2 standard errors, on all
   validation matches as 0005 says. For region calibration, the gain on
   cross-region matches alone is printed as well (most Major matches are
   cross-region), but with under 300 such matches it is too noisy to decide on.
5. The test period is scored once, with the settled model
   (`scripts/fit_model_v1.py --final`). The leaky versions had already been
   scored on it twice; those numbers are void.

## Lesson for later steps
Any field a source fills in after the fact (lists of "best results",
"notable" flags, current rankings) can leak the future into a backtest.
Before using a field, check when it was knowable. (HLTV's ranking filter
passed this check: it uses the ranking at the time of each match; 117
different teams appear, some only in early months.)
