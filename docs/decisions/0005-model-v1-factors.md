# 0005: Factors for Model v1 (Stage 1)

Date: 2026-11-18. Status: accepted (user's choices, made from the options and
analysis below). Amended by 0006: Valve's LAN flags and event weights leak
the future, so LAN status now comes from HLTV and event weighting is on hold.
Test results for every factor: docs/JOURNAL.md, Step 6.

## Rule for every factor
A factor stays in the model only if it improves predictions (log loss) on
past matches the model hasn't seen. A factor that fails the test is removed
and the result is written down here.

## Chosen

| Factor | How it will work | Data support |
|---|---|---|
| **Own rating + VRS points** (core) | Our own Elo-style rating from match results. A small model fitted on past matches decides how much weight goes to it versus Valve's VRS points. | Full |
| **Roster-change reset** | After a lineup change, pull the rating partly back toward average. | Full: Valve's tables list the exact lineup for every match |
| **BO1 vs BO3** | BO1s are more random. Based on the independent-maps assumption, because the data doesn't record match format; checked against past Major Swiss matches where the rules tell us the format. | Indirect |
| **LAN weighting** | LAN results count more. | Partial: LAN flag shown for about 47% of wins, never for losses |
| **Event-strength weighting** | Results at strong events count more. Warned beforehand that an Elo-type rating already gives little credit for beating weak teams, so this may be redundant. | Partial: shown for about 55% of wins |
| **Region calibration** | Learn how strong each region is from cross-region matches, so teams that mostly play at home (e.g. Lynn Vision, Chinggis Warriors, 9z) are placed correctly. | Full |
| **Strength uncertainty** | Teams with little recent data get a wider spread of possible strengths; each simulation draws one value. Changes which ballot is safest more than the average odds. | Full |
| **Per-team curve vs opponent strength** (user's idea) | Whether a team beats the odds more or less as the strength gap grows. See below. | Full |
| **Player ratings, only after roster changes** | Use a new player's rating to estimate a changed lineup. Only if HLTV data is collected. | Needs HLTV |

## The user's opponent-strength idea, made precise
"How a team does against much stronger, similar and much weaker opponents"
breaks into three numbers per team:
1. **Level**: better against everyone. That's the rating itself.
2. **Slope**: better than expected as an underdog *and* worse than expected
   as a favourite (a volatile, "giant-killer" team), or the reverse (a
   consistent, "flat-track bully" team). One extra number per team.
3. **Curvature**: special performance only against similar-strength teams.
   With about 15 matches per bucket per team in 6 months this is pure noise,
   so it isn't modelled.

The slope is shrunk toward "normal" unless the evidence is strong, and it's
kept only if a team's slope measured in one period predicts its results in
the next. The report will still show each team's record against stronger,
similar and weaker opponents in the user's three buckets.

## Not chosen (for Stage 1)
- Inactivity / rust, travel / time zone: not selected.
- Head-to-head, Major experience: not selected.
- Map pool / veto: depends on HLTV access (below).

## Open: HLTV via the user's own computer
The user is trying to connect a folder from their computer (Remote Control)
so their logged-in browser can be used for a small, slow pass over HLTV
(map pools; player ratings for changed lineups). HLTV's terms restrict
automated access, so the scope stays small and the risk is on the user's
account. Scope (current snapshot only, or also pages for past Majors so it
can be tested) is to be decided once the connection works.
