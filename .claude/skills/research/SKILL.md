---
name: research
description: Fetch all Premier League matchweek data from soccerdata (FPL + SofaScore). Run before analyze. Usage: /research [matchweek_number] [local]
---

# Research — Parallel Data Collection for Matchweek

Collect all data for matchweek $ARGUMENTS from soccerdata sources using 3 parallel fetcher agents.

**Local flag**: if the word `local` appears in `$ARGUMENTS`, set `LOCAL_MODE=true` and skip Step 0 entirely.

## Prerequisites

Check that scripts exist:
```bash
ls scripts/soccerdata_client.py
```

## Step 0: GDrive Cache Check

> **Skip this step entirely if `LOCAL_MODE=true`.** Jump straight to Step 1.

Before fetching any data, check Google Drive for cached analysis outputs.

Use Drive MCP tools to navigate the folder tree:
1. List files in My Drive root → find `EPL TOTW Reporter`
2. Inside → find `2025-26`
3. Inside → find `matchweek-{NN}` (zero-padded: `f"matchweek-{N:02d}"`)
4. List files in that matchweek folder

Check whether **both** `players.json` **and** `formation.json` are present.

**Cache HIT** (both files exist):
- Download `players.json` → save to `output/matchweek-$ARGUMENTS/analysis/players.json`
- Download `formation.json` → save to `output/matchweek-$ARGUMENTS/analysis/formation.json`
- Create the `output/matchweek-$ARGUMENTS/analysis/` directory first if it doesn't exist
- Print: `GDrive cache hit ✅ Matchweek $ARGUMENTS — skipping fetch pipeline`
- Jump directly to Step 7 (verify).

**Cache MISS** (either file absent):
- Print: `GDrive cache miss — running full fetch pipeline.`
- Continue with Step 1 below.

**Drive unavailable** (MCP not connected / auth error / folder not found):
- Print: `GDrive unavailable — running full fetch pipeline.`
- Continue with Step 1 below. Never block the pipeline.

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
Run from {PROJECT_ROOT}:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id1} {id2} {id3} {id4}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id1} {id2} {id3} {id4}
Report when done.
```

**Agent 2 prompt:**
```
Matchweek: {N}. Your fixture IDs: {id5} {id6} {id7}
Run from {PROJECT_ROOT}:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id5} {id6} {id7}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id5} {id6} {id7}
Report when done.
```

**Agent 3 prompt:**
```
Matchweek: {N}. Your fixture IDs: {id8} {id9} {id10}
Run from {PROJECT_ROOT}:
  python3 scripts/soccerdata_client.py fetch-players-subset {N} {id8} {id9} {id10}
  python3 scripts/soccerdata_client.py fetch-lineups-subset {N} {id8} {id9} {id10}
Report when done.
```

Wait for all 3 agents to complete before proceeding.

## Step 5: Verify Data

```bash
ls data/2025-26/matchweek-$ARGUMENTS/
```

Expected files:
- `fixtures.json` ✅
- `players_{id}.json` × N fixtures ✅
- `lineups_{id}.json` × N fixtures ✅

## Output Summary

Report back:
```
Research complete for Matchweek {N}:
✅ Fixtures: {N}/10 fetched
✅ Player stats: {N}/10 fetched ({total_players} players) — 3 parallel agents
✅ Lineups: {N}/10 fetched — 3 parallel agents
Data sources: FPL API + SofaScore (via soccerdata)
```
