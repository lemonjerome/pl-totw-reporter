---
name: analyze
description: Analyze Premier League matchweek data to select the best formation and TOTW players. Run after /research. Outputs formation report and player selections. Usage: /analyze [matchweek_number]
---

# Analyze — Formation & Player Selection for Matchweek

Select the TOTW formation and 11 players for matchweek $ARGUMENTS.

## Prerequisites

Verify research data exists:
```bash
ls data/2025-26/matchweek-$ARGUMENTS/fixtures.json
```

If missing, run `/research $ARGUMENTS` first.

## Step 1: Formation Analysis

```bash
python scripts/formation_analyzer.py $ARGUMENTS
```

This will:
- Load lineup data from all fixtures
- Count formation usage among winning teams
- Select the most-used formation, or default to 4-3-3
- Save result to `output/matchweek-{N}/analysis/formation.json`

Report the result:
```
Formation selected: {4-3-3}
Used by winning teams: {3} times
Teams: {Liverpool (4-3-3, won 3-1), Arsenal (4-3-3, won 2-0), Man City (4-3-3, won 4-0)}
Default used: No
```

## Step 2: Player Selection

```bash
python scripts/player_evaluator.py $ARGUMENTS
```

This will:
- For each position in the selected formation, rank all eligible players
- Apply position-appropriate stats from position-roles.md
- Apply minimum 60-minute filter
- Apply tiebreaker logic
- Save result to `output/matchweek-{N}/analysis/players.json`

Report the 11 selected players with their key stat that won them the spot:
```
GK: Jordan Pickford (Everton) — 7 saves, clean sheet
RB: Trent Alexander-Arnold (Liverpool) — 2 assists, 4 key passes
...
```

## Step 3: Report Generation

```bash
python scripts/report_generator.py $ARGUMENTS
```

This will create:
- `output/matchweek-{N}/analysis/formation_report.md` — Why this formation, which teams, results
- `output/matchweek-{N}/analysis/player_reports/{position}.md` — Per player: stats, match context, key moments, why selected
- `output/matchweek-{N}/analysis/summary.md` — High-level TOTW overview for email

## Output Summary

```
Analysis complete for Matchweek {N}:
Formation: {N-N-N}
Players selected:
  GK: {name} ({club})
  RB: {name} ({club})
  CB: {name} ({club})
  CB: {name} ({club})
  LB: {name} ({club})
  CDM: {name} ({club})
  CM: {name} ({club})
  CM: {name} ({club})
  RW: {name} ({club})
  ST: {name} ({club})
  LW: {name} ({club})

Reports saved to: output/matchweek-{N}/analysis/
```
