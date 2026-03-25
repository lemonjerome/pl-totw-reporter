---
name: research
description: Fetch all Premier League matchweek data from soccerdata (FPL + Understat + ESPN) and scrape the PL website for match reports and commentaries. Run before analyze. Usage: /research [matchweek_number]
---

# Research — Parallel Data Collection for Matchweek

Collect all data for matchweek $ARGUMENTS from soccerdata sources using 3 parallel fetcher agents.

## Prerequisites

Check that scripts exist:
```bash
ls scripts/soccerdata_client.py scripts/pl_scraper.py
```

## Step 1: Check Fixture Status

```bash
python3 scripts/soccerdata_client.py check-status $ARGUMENTS
```

Verify all fixtures are complete (status `FT`). If any are `NS` or in-progress, inform the user and do not proceed.

## Step 2: Fetch Fixtures (Sequential — fast)

```bash
python3 scripts/soccerdata_client.py fetch-round $ARGUMENTS
```

Fetches all fixtures from the FPL API and saves to `data/2025-26/matchweek-{N}/fixtures.json`.

After this completes, read `data/2025-26/matchweek-$ARGUMENTS/fixtures.json` and extract all fixture IDs from the `"fixture"."id"` field of each element in the JSON array.

## Step 3: Split Fixtures into 3 Equal Groups

Use floor division + remainder distribution:
1. base = N // 3
2. remainder = N % 3
3. Agent sizes: agent i gets `base + 1` if `i < remainder`, else `base`

Examples:
| N  | base | rem | Agent 1 | Agent 2 | Agent 3 |
|----|------|-----|---------|---------|---------|
| 10 |  3   |  1  | 4 (3+1) | 3       | 3       |
| 9  |  3   |  0  | 3       | 3       | 3       |
| 8  |  2   |  2  | 3 (2+1) | 3 (2+1) | 2       |
| 7  |  2   |  1  | 3 (2+1) | 2       | 2       |

Remainder fixtures are assigned starting from Agent 1, then Agent 2 if needed.

## Step 4: Launch 3 Parallel Fetcher Agents

**CRITICAL**: Spawn all 3 `researcher-fetcher` agents in a **single message** so they run in parallel. Do not wait between them.

Each agent prompt (fill in real IDs from step 3):

**Agent 1 prompt:**
```
Matchweek: {N}. Your fixture IDs: {id1} {id2} {id3} {id4}
Run from /Users/gabrielramos/Desktop/PL-team-builder:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id1} {id2} {id3} {id4}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id1} {id2} {id3} {id4}
Report when done.
```

**Agent 2 prompt:**
```
Matchweek: {N}. Your fixture IDs: {id5} {id6} {id7}
Run from /Users/gabrielramos/Desktop/PL-team-builder:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id5} {id6} {id7}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id5} {id6} {id7}
Report when done.
```

**Agent 3 prompt:**
```
Matchweek: {N}. Your fixture IDs: {id8} {id9} {id10}
Run from /Users/gabrielramos/Desktop/PL-team-builder:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id8} {id9} {id10}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id8} {id9} {id10}
Report when done.
```

Wait for all 3 agents to complete before proceeding.

## Step 5: Scrape Match Reports (after parallel fetch)

```bash
python3 scripts/pl_scraper.py match-reports $ARGUMENTS
```

Save to `data/2025-26/matchweek-{N}/reports/`. Failures are non-blocking.

## Step 6: Scrape Commentaries

```bash
python3 scripts/pl_scraper.py commentaries $ARGUMENTS
```

Save to `data/2025-26/matchweek-{N}/commentaries/`. Failures are non-blocking.

## Step 7: Verify Data

```bash
ls data/2025-26/matchweek-$ARGUMENTS/
```

Expected files:
- `fixtures.json` ✅
- `players_{id}.json` × N fixtures ✅
- `lineups_{id}.json` × N fixtures ✅
- `reports/*.txt` (may be partial) ⚠️
- `commentaries/*.txt` (may be partial) ⚠️

## Output Summary

Report back:
```
Research complete for Matchweek {N}:
✅ Fixtures: {N}/10 fetched
✅ Player stats: {N}/10 fetched ({total_players} players) — 3 parallel agents
✅ Lineups: {N}/10 fetched — 3 parallel agents
✅ Match reports: {X}/10 scraped
✅ Commentaries: {Y}/10 scraped
Data sources: FPL API + Understat + ESPN (via soccerdata)
```
