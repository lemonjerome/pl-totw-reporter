---
name: research
description: Fetch all Premier League matchweek data from soccerdata (FPL + Understat + ESPN) and scrape the PL website for match reports and commentaries. Run before analyze. Usage: /research [matchweek_number]
---

# Research — Data Collection for Matchweek

Collect all data for matchweek $ARGUMENTS from soccerdata sources and the PL website.

## Prerequisites

Check that scripts exist:
```bash
ls scripts/soccerdata_client.py scripts/pl_scraper.py
```

## Step 1: Check Fixture Status

```bash
python scripts/soccerdata_client.py check-status $ARGUMENTS
```

Verify all 10 fixtures are complete (status `FT`). If any are `NS` or in-progress, inform the user and do not proceed.

## Step 2: Fetch Fixtures

```bash
python scripts/soccerdata_client.py fetch-round $ARGUMENTS
```

This will:
- Fetch fixtures from the FPL API for the matchweek
- Save to `data/2025-26/matchweek-{N}/fixtures.json` in API-Football-compatible format
- Return: list of fixture IDs and their statuses

Verify all 10 fixtures are returned. If a fixture has status `PST` (postponed), note it.

## Step 3: Fetch Player Stats

```bash
python scripts/soccerdata_client.py fetch-players $ARGUMENTS
```

This will:
- Fetch Understat (goals, assists, key_passes, minutes) and ESPN (saves, shots_on_target, formation) in parallel per fixture
- Save to `data/2025-26/matchweek-{N}/players_{fixture_id}.json` for each fixture
- Return: all player stats for both teams

**Note**: Tackles, interceptions, blocks are not available from soccerdata sources. CB/CDM selection will use available stats.

**Performance**: First run ~4–5 minutes (network). Warm soccerdata cache ~30–60s. See `.claude/rules/soccerdata.md` for details.

## Step 4: Fetch Lineups

```bash
python scripts/soccerdata_client.py fetch-lineups $ARGUMENTS
```

This will:
- Fetch ESPN lineup data (formation string + starting XI) for each fixture
- Save to `data/2025-26/matchweek-{N}/lineups_{fixture_id}.json`

## Step 5: Scrape Match Reports

```bash
python scripts/pl_scraper.py match-reports $ARGUMENTS
```

This will:
- Navigate to the PL website for each fixture
- Extract match report text
- Save to `data/2025-26/matchweek-{N}/reports/`

If scraping fails for a fixture, log the failure and continue. Missing reports should not block the process.

## Step 6: Scrape Commentaries

```bash
python scripts/pl_scraper.py commentaries $ARGUMENTS
```

This will:
- Navigate to each match's Commentary tab
- Extract commentary text
- Save to `data/2025-26/matchweek-{N}/commentaries/`

## Step 7: Verify Data

Check all expected files exist:
```bash
ls data/2025-26/matchweek-$ARGUMENTS/
```

Expected:
- `fixtures.json` ✅
- `players_{id}.json` × 10 ✅
- `lineups_{id}.json` × 10 ✅
- `reports/*.txt` (may be partial) ⚠️
- `commentaries/*.txt` (may be partial) ⚠️

## Output Summary

Report back:
```
Research complete for Matchweek {N}:
✅ Fixtures: 10/10 fetched
✅ Player stats: 10/10 fetched ({total_players} players)
✅ Lineups: 10/10 fetched
✅ Match reports: {X}/10 scraped
✅ Commentaries: {Y}/10 scraped
Data sources: FPL API + Understat + ESPN (via soccerdata)
```
