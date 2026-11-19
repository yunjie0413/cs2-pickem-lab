# 0007: Factors are selected by backward elimination

Date: 2026-11-18. Status: accepted (user's choice, made before any
alternative was run, so it couldn't follow from which factors it keeps).
Amends 0005's "Rule for every factor".

## Why
Decision 0005 tested every factor once, each switched off from the
all-factors model, and dropped every factor below 2 standard errors. When
HLTV player ratings were added (journal Step 7a), they and time decay turned
out to overlap: both handle "this team just changed". With both in the
model each looked useless, so that rule dropped both, although player
ratings improved the all-factors model (validation 0.6619 → 0.6587) and
time decay was a clear keep in Step 6.

## Options considered
1. **Backward elimination** (chosen): remove the weakest factor (lowest
   gain / standard error), re-tune, test the rest again; stop when every
   remaining factor clears 2 standard errors. Standard when factors overlap.
2. Keep the one-at-a-time rule: region only; known to drop both of two
   overlapping factors.
3. Player ratings only as an add-on to the Step 6 model: favours whichever
   factor was tested first.
4. Overlapping factors tested as a group, then the best combination chosen
   on validation: more choices made on validation, so more optimistic.

## Rule now
Same bar (2 standard errors), same data (tuned on training, judged on all
validation matches), applied to all factors in `scripts/fit_model_v1.py`
step [2]. The test period is still scored only once, at the end.

## Amendment, 2026-11-19: every model is tuned until it stops improving
The first backward-elimination run removed every factor, region included,
but its comparison models had one coordinate-search pass each and were noisy
by about ±0.001–0.002, the size of the effects tested (journal Step 7a). The
user chose, before any re-run, from: tune fully and keep the rule (chosen);
accept no factors; tune fully and judge region on cross-region matches
only; drop the 2-SE bar and pick the best of all 32 combinations on
validation. Now every tuning (full model, each comparison model, selected
and final model) repeats its passes until a whole pass finds nothing better
(at most 10). Whatever this keeps stands, even if it is still nothing.
