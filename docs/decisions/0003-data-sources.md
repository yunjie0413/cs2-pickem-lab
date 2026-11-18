# 0003: Data sources

Date: 2026-11-18. Status: accepted for now; revisit when choosing factors.

## Options considered

| Source | What it has | Problems |
|---|---|---|
| **Valve VRS repo** ([counter-strike_regional_standings](https://github.com/ValveSoftware/counter-strike_regional_standings)) | Monthly snapshots since 2024. Each roster's page lists every counted match over the last 6 months: date, opponent, W/L, LAN, event weight, roster. Also Valve's points and model code. | Match level only: no maps or scores. Only matches Valve counts. Team identity is roster-based (good for roster changes, but names get duplicated). |
| **HLTV** | Everything, including maps, scores and player stats | No public API. Its terms don't allow automated scraping, and it sits behind Cloudflare bot protection. Having an account doesn't change either. |
| **Liquipedia** | Brackets, results, rosters | Blocked by this cloud environment's network policy right now. Its API has usage terms (rate limits, attribution). |
| **Betting odds** | Best single predictor of match results | No free clean source. Maybe enter round 1 odds by hand later, as a benchmark. |

## Decision
- **Primary:** the VRS repo. It's official, versioned and legal to use, and
  its dated snapshots let us backtest without leaking future results.
- **HLTV:** manual lookups only (e.g. a hand-filled CSV of map pools for the
  16 teams) if a factor turns out to need it. No scraper.
- Revisit map-level data when we decide on a map/veto model.

## Consequences
- Model v1 is match-level (series results), not map-level.
- The BO1 vs BO3 conversion relies on an assumption (independent maps) until
  we have map data. See pickem/baseline.py.
