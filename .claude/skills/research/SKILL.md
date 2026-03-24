---
name: research
description: Fetch all Premier League matchweek data from API-Football and scrape the PL website for match reports and commentaries. Run before analyze. Usage: /research [matchweek_number]
---

# Research — Data Collection for Matchweek

Collect all data for matchweek $ARGUMENTS from API-Football and the PL website.

## Prerequisites

Check that scripts exist:
```bash
ls scripts/api_football.py scripts/pl_scraper.py
```

Check daily API budget:
```bash
python scripts/api_football.py check-budget
```

## Step 1: Fetch Fixtures

```bash
python scripts/api_football.py fetch-round $ARGUMENTS
```

This will:
- Call `/fixtures?league=39&season=2025&round=Regular Season - {N}`
- Save to `data/2025-26/matchweek-{N}/fixtures.json`
- Return: list of fixture IDs and their statuses

Verify all 10 fixtures are returned. If a fixture has status `PST` (postponed), note it — it may affect formation/player counts.

## Step 2: Fetch Player Stats

For each fixture ID returned in Step 1:
```bash
python scripts/api_football.py fetch-players {fixture_id}
```

This will:
- Call `/fixtures/players?fixture={fixture_id}`
- Save to `data/2025-26/matchweek-{N}/players_{fixture_id}.json`
- Return: all player stats for both teams

Run this for all 10 fixtures. If a fixture was postponed, skip it.

## Step 3: Fetch Lineups (if needed)

If formation data is not available in the fixtures response:
```bash
python scripts/api_football.py fetch-lineups {fixture_id}
```

Save to `data/2025-26/matchweek-{N}/lineups_{fixture_id}.json`

## Step 4: Scrape Match Reports

```bash
python scripts/pl_scraper.py match-reports $ARGUMENTS
```

This will:
- Navigate to the PL website for each fixture
- Extract match report text
- Save to `data/2025-26/matchweek-{N}/reports/`

If scraping fails for a fixture, log the failure and continue. Missing reports should not block the process.

## Step 5: Scrape Commentaries

```bash
python scripts/pl_scraper.py commentaries $ARGUMENTS
```

This will:
- Navigate to each match's Commentary tab
- Extract commentary text
- Save to `data/2025-26/matchweek-{N}/commentaries/`

## Step 6: Verify Data

Check all expected files exist:
```bash
ls data/2025-26/matchweek-$ARGUMENTS/
```

Expected:
- `fixtures.json` ✅
- `players_{id}.json` × 10 ✅
- `reports/*.txt` (may be partial) ⚠️
- `commentaries/*.txt` (may be partial) ⚠️

## Output Summary

Report back:
```
Research complete for Matchweek {N}:
✅ Fixtures: 10/10 fetched
✅ Player stats: 10/10 fetched ({total_players} players)
✅ Match reports: {X}/10 scraped
✅ Commentaries: {Y}/10 scraped
API requests used today: {count}/100
```
