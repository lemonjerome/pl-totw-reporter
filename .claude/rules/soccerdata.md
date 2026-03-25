# soccerdata — Integration Guide (2025-26 Season)

## Why soccerdata

API-Football free plan only covers seasons 2022–2024. For 2025-26 PL data we use `soccerdata` (v1.8+), which scrapes multiple public sources. No API key required, no daily budget.

## Architecture: Three Sources Combined

| Source | What it provides | Season param |
|--------|-----------------|-------------|
| FPL API (`fantasy.premierleague.com`) | Fixtures, scores, matchweek mapping, team IDs | N/A (always current) |
| Understat | Goals, assists, key_passes, minutes, xG, xA | `2025` (start-year convention) |
| ESPN (`soccerdata.ESPN`) | Saves, shots_on_target, formation_place, sub times, formation string | `2026` (end-year convention) |

FBref is **blocked** (403 Forbidden on all requests). Do not attempt to use it.

## Client Script

Always use `scripts/soccerdata_client.py`. Never scrape sources directly.

```bash
python scripts/soccerdata_client.py check-budget          # No daily limit — just shows cache info
python scripts/soccerdata_client.py check-status 33       # Fixture statuses for matchweek 33
python scripts/soccerdata_client.py fetch-round 33        # Fetch all fixtures for matchweek 33
python scripts/soccerdata_client.py fetch-players 33      # Fetch player stats for matchweek 33
python scripts/soccerdata_client.py fetch-lineups 33      # Fetch lineup/formation for matchweek 33
```

## Season Constants

```python
UNDERSTAT_SEASON = 2025   # Understat uses start year: 2025 = 2025-26
ESPN_SEASON = 2026         # ESPN uses end year: 2026 = 2025-26
```

## Output Format

All cached files use **API-Football nested JSON format** — identical to what `api_football.py` produces — so `formation_analyzer.py` and `player_evaluator.py` work unmodified.

```
data/
  2025-26/
    matchweek-{N}/
      fixtures.json              # FPL fixtures in API-Football format
      players_{fixture_id}.json  # Player stats merged from Understat + ESPN
      lineups_{fixture_id}.json  # Formation + starting XI from ESPN
```

## Known Data Limitations

| Stat | Available | Source |
|------|-----------|--------|
| Goals | ✅ | Understat |
| Assists | ✅ | Understat |
| Key passes | ✅ | Understat |
| Minutes played | ✅ | ESPN (sub_in/sub_out) |
| Shots on target | ✅ | ESPN |
| Saves | ✅ | ESPN |
| Formation | ✅ | ESPN |
| xG / xA | ✅ | Understat (stored but not used in selection) |
| **Tackles** | ❌ | Not available from any working source |
| **Interceptions** | ❌ | Not available |
| **Blocks** | ❌ | Not available |
| **Pass accuracy** | ❌ | Not available |
| **API rating** | ❌ | Not available (shows N/A in output) |

**Impact**: CB and CDM selection falls back to goals_conceded (GK/CB) and key_passes. Selection quality for defensive positions is lower than with API-Football data.

## Performance

| Run type | Time |
|----------|------|
| First run (cold soccerdata cache) | ~4–5 minutes (network I/O) |
| Warm soccerdata cache, no project cache | ~30–60 seconds |
| Warm project cache | < 1 second |

**Two cache layers**:
1. `~/soccerdata/data/` — raw HTTP responses cached by soccerdata library
2. `data/2025-26/matchweek-{N}/` — processed API-Football-format project cache

Parallelism: Understat and ESPN are fetched concurrently per fixture via `ThreadPoolExecutor(max_workers=2)`.

## Team Name Normalization

Each source uses different team names. The client has three lookup tables mapping to canonical names used throughout the project:

- `FPL_TO_CANONICAL` — e.g. `"Nott'm Forest"` → `"Nottm Forest"`
- `UNDERSTAT_TO_CANONICAL` — e.g. `"Manchester City"` → `"Man City"`
- `ESPN_TO_CANONICAL` — e.g. `"AFC Bournemouth"` → `"Bournemouth"`

2025-26 promoted teams in FPL: Burnley (id=3), Leeds (id=11), Sunderland (id=17).

## Player Deduplication

Understat and ESPN sometimes return slightly different name spellings for the same player (e.g. "Toti" vs "Toti Gomes"). The client deduplicates by name containment within the same team, keeping the entry with more complete stats.

## Error Handling

- **403 from FBref**: Expected — do not retry, FBref is blocked.
- **Empty Understat result**: Some fixtures return no data. Affected players get zeros for attacking stats.
- **ESPN schedule lookup miss**: Use ESPN's numeric `game_id` column, not the index string.
- **Stale project cache**: If `fixtures.json` is in old Pydantic format (no `"fixture"` key), it is auto-deleted and re-fetched.
