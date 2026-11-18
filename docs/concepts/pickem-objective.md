# Choosing a ballot: P(≥5 correct) vs expected correct picks

## The short version

- **Expected correct picks** = the sum of each pick's own probability. You can
  compute it from per-team probabilities alone ("NiP goes 3-0 with 24%"...).
- **P(≥5 correct)** depends on how the picks succeed or fail *together*.
  Per-team probabilities can't give you that. You need the joint outcome of
  the whole stage, and the simulation gives it to you for free.

The Pick'Em rewards 5+ correct. Nothing extra for 8 instead of 5, and
nothing for 4. So P(≥5) is the right target.

## How it's computed (no formula needed)

1. Simulate the stage 100,000 times. Each simulation is one complete stage:
   every match result, every team's final record.
2. For a candidate ballot, grade it in every simulation: count its correct
   picks in that simulated stage.
3. P(≥5) = the fraction of simulations where the count was 5 or more.

The expected count comes from the same grading: it's the average count. So
both objectives come from the same table. They just summarise it differently.

## A worked example where they disagree

Suppose your 6 advance picks and 2 0-3 picks always give exactly 4 correct
(an unrealistic simplification to keep the arithmetic easy). The ballot then
hinges on the two 3-0 picks. You need at least one of them.

Three strong teams each go 3-0 with probability 30%. X and Y are in the same
part of the bracket: if both reach 2-0, they play each other, so **at most
one of them can go 3-0**. Z is in a different part of the bracket and is
(roughly) independent of X.

| 3-0 picks | Expected correct | P(at least one 3-0 hits) | P(≥5) |
|---|---|---|---|
| X + Y | 4 + 0.3 + 0.3 = **4.6** | 0.3 + 0.3 = **60%** (they can't both hit, so no overlap) | **60%** |
| X + Z | 4 + 0.3 + 0.3 = **4.6** | 1 − 0.7 × 0.7 = **51%** | **51%** |

Expected count says the two ballots are equal. P(≥5) says X + Y is clearly
better: negatively correlated picks are a hedge.

Now flip it. If your other 8 picks give exactly **3** correct, you need
**both** 3-0 picks to hit. X + Y can never do that (0%), while X + Z hits
both with 0.3 × 0.3 = 9%. The best pair depends on the rest of the ballot,
which expected count can't see.

General rule of thumb:
- If your ballot's expected count is **above** 5, P(≥5) prefers safe,
  hedged (low-variance) picks.
- If it's **below** 5, P(≥5) prefers picks that tend to succeed together
  (high variance). You need some luck anyway, so concentrate it.

## Where correlation comes from in a Swiss stage

- **The bracket itself.** Exactly 2 teams go 3-0 and exactly 2 go 0-3 in
  every stage. Teams who would meet in the 2-0 or 0-2 match can't both get
  those records. One team's upset sends its opponent down a different path.
- **Model error.** If the model overrates one team, every pick involving that
  team or its opponents is off at the same time. Drawing team strengths once
  per simulation (planned, see the journal) builds this in.

## How the optimizer searches

About 10 million ballots exist (120 × 91 × 924). `best_threshold()` restricts
each slot to its top candidates (top 6 for 3-0, top 6 for 0-3, top 10 for
advance) and grades every ballot built from them, around 40k ballots. That
takes a few seconds with numpy.

**Winner's curse.** When you pick the best of 40k noisy estimates, the
winner's score is biased upward: part of why it won is luck in those
particular simulations. So the top 20 ballots are re-graded on a **fresh,
independent** set of simulations (`confirm()`), and that number is the one
reported.

## What we actually saw for Singapore Stage 1 (Baseline 0)

With the VRS-points baseline, both objectives chose almost the same ballot
(37.3% vs 37.4% success, a statistical tie). That's expected here: the
baseline is very flat (seeds 1–8 are within about 75 VRS points of each other),
so correlations barely change which ballot is best. The two objectives
diverge more when the model is confident about a few teams and the bracket
creates strong dependencies. We keep P(≥5) as the objective because it's
the correct target; it simply costs nothing when the two agree.
