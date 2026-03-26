---
name: presentation
description: Create a PL-styled presentation for the TOTW and export to PDF using python-pptx + Playwright. Includes results, team diagram, formation report, player slides, and next fixtures. Run after /visualize. Usage: /presentation [matchweek_number]
---

# Presentation — TOTW Report

Create the TOTW presentation for matchweek $ARGUMENTS using `scripts/presentation_builder.py`.

## Prerequisites

Verify required files exist before running:
```bash
ls output/matchweek-$ARGUMENTS/totw_diagram.png
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/analysis/formation.json
```

If any are missing, run the earlier pipeline stages first (`/research`, `/analyze`, `/visualize`).

## Step 1: Run the Presentation Builder

```bash
python scripts/presentation_builder.py $ARGUMENTS
```

This creates two files:
- `output/matchweek-{N}/presentation.pdf` — high-quality PDF (Playwright HTML rendering)
- `output/matchweek-{N}/presentation.pptx` — editable PowerPoint file (python-pptx)

## Slide Structure

The presentation always follows this 17-slide structure:

| # | Slide | Content |
|---|-------|---------|
| 1 | Title | "Team of the Week · Matchweek N" on PL purple background |
| 2 | Results | All 10 match results with team badges and scores |
| 3 | Section | "FORMATION" section divider (magenta gradient) |
| 4 | Formation | Formation name, usage stats, winning teams, rationale |
| 5 | Section | "PLAYERS" section divider (magenta gradient) |
| 6–16 | Player | 1 per player (GK → defenders → midfielders → attackers) |
| 17 | Diagram | TOTW pitch diagram (left) + Next matchweek fixtures (right) |

## Player Slide Layout

Each player slide has:
- **Left**: Circular photo with green border, team badge overlay, nationality flag, name, position label
- **Right**: Position title (magenta), player name, key stat (green), stats grid with 6 metrics

Position-specific stats displayed:
- GK: Saves, Goals Conceded, Clean Sheet, Minutes, Rating
- CB: Tackles Won, Interceptions, Clearances, Aerial Duels Won, Blocks, Rating
- RB/LB: Defensive Actions, Key Passes, Assists, Tackles, Interceptions, Rating
- CDM: Tackles Won, Interceptions, Clearances, Duels Won, Pass Accuracy, Rating
- CM/CAM: Key Passes, Goals, Assists, Pass Accuracy, Tackles, Rating
- RM/LM/RW/LW: Goals, Assists, Key Passes, Dribbles, Shots on Target, Rating
- ST/CF: Goals, Shots on Target, Assists, Shot Conversion, Total Shots, Rating

## Next Matchweek Fixtures

The last slide shows next matchweek fixtures from `data/2025-26/matchweek-{N+1}/fixtures.json`.
- If that file doesn't exist, the slide shows "Next matchweek fixtures not yet available."
- Dates are displayed without scores, even if the matchweek has already been played.

## Output Confirmation

```
Building presentation for matchweek {N}...
  Formation:  4-2-3-1
  Players:    11
  Fixtures:   10

→ Building PDF (HTML + Playwright)...
  PDF saved:  output/matchweek-{N}/presentation.pdf (3.7 MB)

→ Building PPTX (python-pptx)...
  PPTX saved: output/matchweek-{N}/presentation.pptx (2.0 MB)

Done.
```
