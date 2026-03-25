# soccerdata — Integration Guide (2025-26 Season)

## Why soccerdata

API-Football free plan only covers seasons 2022–2024. For 2025-26 PL data we use `soccerdata` (v1.8+) for schedule lookup, plus the SofaScore direct API for all player stats. No API key required, no daily budget.

## Architecture: Two Sources

| Source | What it provides | Notes |
|--------|-----------------|-------|
| FPL API (`fantasy.premierleague.com`) | Fixtures, scores, matchweek mapping, team IDs | No key needed, always current |
| SofaScore API (`api.sofascore.com/api/v1/event/{id}/lineups`) | All 66 player stats per match: goals, assists, key_passes, minutes, tackles, interceptions, clearances, blocks, aerial duels, pass accuracy, player rating, xG/xA, plus formation string | 1 call per fixture; accessed via `tls_requests` (installed as soccerdata dependency) |
| `soccerdata.Sofascore` (schedule only) | game_id lookup to map FPL fixtures → SofaScore event IDs | Cached to `data/sofascore_schedule_2526.json` |

FBref is **blocked** (403 Forbidden on all requests). Do not attempt to use it.

## Client Script

Always use `scripts/soccerdata_client.py`. Never call APIs directly.

```bash
python scripts/soccerdata_client.py check-budget          # No daily limit — just shows cache info
python scripts/soccerdata_client.py check-status 33       # Fixture statuses for matchweek 33
python scripts/soccerdata_client.py fetch-round 33        # Fetch all fixtures for matchweek 33
python scripts/soccerdata_client.py fetch-players 33      # Fetch player stats for matchweek 33
python scripts/soccerdata_client.py fetch-lineups 33      # Fetch lineup/formation for matchweek 33
```

## Season Constants

```python
SOFASCORE_SEASON = "2526"   # soccerdata.Sofascore season format: "2526" = 2025-26
```

## How SofaScore Works

`fetch_players()` makes a single call per fixture to `/event/{game_id}/lineups` and writes **both** `players_{id}.json` and `lineups_{id}.json` from the same response. `fetch_lineups()` reads from this cache; if missing, delegates to `fetch_players`.

Game IDs are resolved via `soccerdata.Sofascore.read_schedule()`, cached to `data/sofascore_schedule_2526.json`. Team name mapping uses `SOFASCORE_TO_CANONICAL`.

## Output Format

All cached files use **API-Football nested JSON format** — identical to what `api_football.py` produces — so `formation_analyzer.py` and `player_evaluator.py` work unmodified.

```
data/
  2025-26/
    sofascore_schedule_2526.json   # Full season schedule with SofaScore game_ids
    matchweek-{N}/
      fixtures.json                # FPL fixtures in API-Football format
      players_{fixture_id}.json    # Player stats from SofaScore
      lineups_{fixture_id}.json    # Formation + starting XI from SofaScore
```

## Available Stats (SofaScore)

| Stat | Available | SofaScore field |
|------|-----------|----------------|
| Goals | ✅ | `goals` |
| Assists | ✅ | `goalAssist` |
| Key passes | ✅ | `keyPass` |
| Minutes played | ✅ | subbedInAt / subbedOutAt |
| Shots on target | ✅ | `onTargetScoringAttempt` |
| Shots total | ✅ | on + off + blocked |
| Saves | ✅ | `saves` |
| Formation | ✅ | `formation` (direct string e.g. "4-3-3") |
| xG / xA | ✅ | `expectedGoals`, `expectedAssists` (stored, not used in selection) |
| **Tackles won** | ✅ | `wonTackle` |
| **Interceptions** | ✅ | `interceptionWon` |
| **Clearances** | ✅ | `totalClearance` |
| **Blocks** | ✅ | `outfielderBlock` |
| **Aerial duels won/lost** | ✅ | `aerialWon`, `aerialLost` |
| **Duels won** | ✅ | `duelWon` |
| **Pass accuracy** | ✅ | computed from `accuratePass` / `totalPass` |
| **Accurate crosses** | ✅ | `accurateCross` |
| **Player rating** | ✅ | `rating` (float, e.g. 7.4) |

## Performance

| Run type | Time |
|----------|------|
| No project cache (first fetch) | ~15–20 seconds per matchweek (10 fixtures × 1s SofaScore delay) |
| Warm project cache | < 1 second |

**Cache layer**: `data/2025-26/matchweek-{N}/` — processed project cache. Once written, subsequent runs are instant. SofaScore is rate-limited to 1 call/second (polite delay in `fetch_players`).

## Team Name Normalization

Two lookup tables map team names to canonical names used throughout the project:

- `FPL_TO_CANONICAL` — e.g. `"Nott'm Forest"` → `"Nottm Forest"`
- `SOFASCORE_TO_CANONICAL` — e.g. `"Manchester City"` → `"Man City"`, `"AFC Bournemouth"` → `"Bournemouth"`

2025-26 promoted teams in FPL: Burnley (id=3), Leeds (id=11), Sunderland (id=17).

## Error Handling

- **SofaScore 403**: Use `tls_requests` (not standard urllib/requests) — SofaScore blocks standard TLS fingerprints.
- **SofaScore game_id not found**: Schedule cache may be stale — delete `data/sofascore_schedule_2526.json` and re-fetch.
- **Stale project cache**: If `fixtures.json` is in old Pydantic format (no `"fixture"` key), it is auto-deleted and re-fetched.
- **Missing lineups**: `fetch_lineups()` automatically calls `fetch_players()` for any fixture where the lineup cache is missing.
