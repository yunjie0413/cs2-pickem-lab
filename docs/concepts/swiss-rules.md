# Valve Major Swiss rules and how the code implements them

Source: Valve's Major Supplemental Rulebook,
[ValveSoftware/counter-strike_rules_and_regs](https://github.com/ValveSoftware/counter-strike_rules_and_regs/blob/main/major-supplemental-rulebook.md)
at commit `621b7d9` (2026-10-07). Re-check before each Major; Valve changes
these rules from time to time.

| Rule (quoted or paraphrased from the rulebook) | Code |
|---|---|
| 16 teams. Three wins advance, three losses eliminate. Teams only play opponents with the same W-L record. | `SwissState.pools()` groups active teams by record |
| "All elimination and advancement matches are to be best of three. All other matches are to be best of one." | `is_best_of_three()`: BO3 when the teams are at 2 wins or 2 losses |
| Round 1: seed 1 v 9, 2 v 10, …, 8 v 16 | `ROUND1_PAIRS` |
| "In round 2 and 3, the highest seeded team faces the lowest seeded team available that does not result in a rematch within the stage." | `_pair_high_vs_low()` |
| "In other rounds, refer to the following table and select the top-most row that does not result in a rematch" (15-row table for pools of 6) | `PRIORITY_TABLE`, `_pair_by_priority_table()` |
| Mid-stage seed = (1) current W-L record, (2) Difficulty Score, (3) initial seed of the current stage | sort key in `SwissState.pools()` |
| Difficulty Score (Buchholz) = sum of current wins minus losses of every opponent faced | `SwissState.buchholz()` |
| Stage 1 initial seeds = VRS global standing order | `data/events/*.json` `seed` field |

## Interpretation choices (the rulebook is silent on these)

1. **Dead ends in rounds 2–3.** If the greedy "highest vs lowest available"
   choice would force a later rematch, the code backtracks and gives the
   higher seed the next-lowest opponent. This reads "if possible" literally.
   It's rare; it can only happen in the 1-1 pool of round 3.
2. **No rematch-free option at all.** Rounds 2–3 fall back to plain high vs
   low; rounds 4–5 fall back to row 1 of the table. This is probably
   impossible with 16 teams, but the code must do something.
3. **Difficulty Score timing.** It's computed from opponents' records at the
   moment of pairing (after the previous round finished). That's the
   rulebook's "current" wins and losses.

## Facts the tests check

- Every stage produces exactly two 3-0, three 3-1, three 3-2, three 2-3,
  three 1-3 and two 0-3 teams.
- 33 matches per stage: 20 BO1 (rounds 1–2 and the 1-1 pool of round 3) and
  13 BO3. No rematches.
- The rulebook's own Difficulty Score example gives 2.
- If the higher seed always wins, round 2 is 1v8, 2v7, 3v6, 4v5 (and 9v16, …)
  and seeds 1 and 2 go 3-0.

## Pick'Em scoring (event-specific, check in-game before locking)

The current Major Pick'Em has 10 picks per Swiss stage: 2 for 3-0, 6 for
"advances with 3-1 or 3-2", 2 for 0-3. A team picked to advance that goes
3-0 does **not** count. 5+ correct completes the stage. Configured in
`pickem/ballot.py` → `BallotRules`.
