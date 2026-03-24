# API-Football v3 — Integration Guide

## Authentication

- **Base URL**: `https://v3.football.api-sports.io`
- **Auth header**: `x-apisports-key: {API_FOOTBALL_KEY}`
- **Rate limit**: 100 requests/day (free tier). Tracked in `data/.api_usage.json`.
- **Always**: Check cache in `data/2025-26/matchweek-{N}/` before making any API call.
- **Never**: Call the API directly — always use `scripts/api_football.py`.

## PL Constants

- **League ID**: `39` (English Premier League)
- **Season**: `2024` (2024-25 season — free plan covers up to 2024; upgrade for 2025-26)
- **Rounds format**: `"Regular Season - {N}"` (e.g., `"Regular Season - 30"`)

## Key Endpoints

### Get Current Round
```
GET /fixtures/rounds?league=39&season=2025&current=true
```
Returns: Array with the current round string, e.g. `["Regular Season - 31"]`

### Get All Fixtures for a Round
```
GET /fixtures?league=39&season=2025&round=Regular Season - {N}
```
Returns: Array of fixture objects with full match data including teams, scores, status, date.

**Fixture status codes**:
- `NS` — Not Started
- `1H` — First Half (live)
- `HT` — Half Time (live)
- `2H` — Second Half (live)
- `ET` — Extra Time (live)
- `BT` — Break Time (live)
- `P` — Penalties (live)
- `SUSP` — Suspended
- `INT` — Interrupted
- `FT` — Full Time ✅ completed
- `AET` — After Extra Time ✅ completed
- `PEN` — After Penalties ✅ completed
- `PST` — Postponed
- `CANC` — Cancelled
- `ABD` — Abandoned

A matchweek is **complete** when all fixtures have status `FT`, `AET`, or `PEN`.

### Get Player Stats for a Fixture
```
GET /fixtures/players?fixture={fixture_id}
```
Returns: Both teams' players with full stats for that match. **This is the most important endpoint** — returns all player stats in 1 request.

**Returns per player**:
```json
{
  "player": {
    "id": 123,
    "name": "Player Name",
    "photo": "https://media.api-sports.io/football/players/123.png"
  },
  "statistics": [{
    "games": {
      "minutes": 90,
      "position": "F",
      "rating": "7.8",
      "captain": false
    },
    "goals": {
      "total": 1,
      "conceded": 0,
      "assists": 1,
      "saves": null
    },
    "shots": {
      "total": 3,
      "on": 2
    },
    "passes": {
      "total": 45,
      "key": 3,
      "accuracy": "87"
    },
    "tackles": {
      "total": 2,
      "blocks": 1,
      "interceptions": 1
    },
    "duels": {
      "total": 8,
      "won": 5
    },
    "dribbles": {
      "attempts": 4,
      "success": 3,
      "past": null
    },
    "fouls": {
      "drawn": 2,
      "committed": 1
    },
    "cards": {
      "yellow": 0,
      "red": 0
    },
    "penalty": {
      "won": 0,
      "committed": 0,
      "scored": 0,
      "missed": 0,
      "saved": 0
    }
  }]
}
```

### Get Fixture Lineups (Formation + Starting XI)
```
GET /fixtures/lineups?fixture={fixture_id}
```
Returns: Both teams' formations (e.g. `"4-3-3"`) and starting XI with grid positions.

**Formation string**: Available as `response[].formation` (e.g., `"4-3-3"`)

**Grid positions**: Each player has `grid` field like `"1:1"` (row:column from defense line)

### Get Fixture Statistics (Team-level)
```
GET /fixtures/statistics?fixture={fixture_id}
```
Returns: Team-level stats (possession, shots, corners, fouls, etc.). Useful for context in reports.

## Request Budget Strategy

Per matchweek (10 fixtures in PL), use this sequence:

| Step | Endpoint | Calls | Purpose |
|------|----------|-------|---------|
| 1 | `/fixtures/rounds?current=true` | 1 | Get current round |
| 2 | `/fixtures?league=39&season=2025&round=...` | 1 | All 10 fixtures at once |
| 3 | `/fixtures/players?fixture={id}` | 10 | Player stats per fixture |
| 4 | `/fixtures/lineups?fixture={id}` | 10 (optional, if lineup not in fixtures) | Formation data |
| **Total** | | **~12-22** | Well within 100/day |

**Optimization**: The `/fixtures` endpoint returns basic lineup and formation data. Only call `/fixtures/lineups` if formation data is missing from the fixtures response.

## Image CDN URLs

Use these CDN URLs for badges and images in the diagram and slides:

```
Team badge:   https://media.api-sports.io/football/teams/{team_id}.png
Player photo: https://media.api-sports.io/football/players/{player_id}.png
Country flag: https://media.api-sports.io/flags/{country_code_2letter}.svg
```

Country codes are ISO 3166-1 alpha-2 (lowercase): `gb-eng` for England, `fr` for France, `es` for Spain, `de` for Germany, `br` for Brazil, etc.

Note: Some country codes from API-Football use specific formats: England = `gb-eng`, Scotland = `gb-sct`, Wales = `gb-wls`, Northern Ireland = `gb-nir`.

## Caching Convention

All responses must be cached to conserve the daily limit:

```
data/
  2025-26/
    matchweek-{N}/
      fixtures.json           # All fixtures for the round
      players_{fixture_id}.json  # Player stats per fixture
      lineups_{fixture_id}.json  # Lineup data per fixture
  .api_usage.json             # Daily request counter {date: count}
```

Before any API call, check if the cached file exists and is non-empty. If it exists, load from cache — do NOT make an API call.

## Error Handling

- `401`: Invalid API key — check `API_FOOTBALL_KEY` env var
- `429`: Rate limit exceeded — stop all API calls for the day, work from cache
- `404`: Fixture/league not found — verify league ID and season
- Empty response `response: []`: Round not found, check round string format

## Round String Format

Important: The round parameter must be exactly: `"Regular Season - N"` where N is the matchweek number (no leading zeros).

Example: `Regular Season - 30` (not `Regular Season - 030`)
