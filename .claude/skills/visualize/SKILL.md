---
name: visualize
description: Generate the TOTW team formation diagram as a high-quality PNG image. Shows players at their positions on a football pitch with team badges, player names, nationality flags, and connecting lines. Run after /analyze. Usage: /visualize [matchweek_number]
---

# Visualize — Team Diagram Generation

Generate the TOTW formation diagram PNG for matchweek $ARGUMENTS.

## Prerequisites

Verify analysis data exists:
```bash
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/analysis/formation.json
```

If missing, run `/analyze $ARGUMENTS` first.

## Step 1: Generate Diagram

```bash
python scripts/diagram_renderer.py $ARGUMENTS
```

This script will:
1. Load `output/matchweek-{N}/analysis/players.json` and `formation.json`
2. Load the formation coordinate map from `.claude/rules/formations.md`
3. Render `templates/pitch.html` with Jinja2 using player data:
   - Position coordinates for each player slot
   - Team badge URL: `https://media.api-sports.io/football/teams/{team_id}.png`
   - Player name
   - Flag URL: `https://media.api-sports.io/flags/{country_code}.svg`
4. Open the rendered HTML in Playwright (headless Chromium)
5. Take a screenshot at 1200×800px
6. Save to `output/matchweek-{N}/totw-diagram.png`

## Step 2: Verify Output

```bash
ls -la output/matchweek-$ARGUMENTS/totw-diagram.png
```

Check that:
- File exists and is > 100KB (if too small, rendering may have failed)
- Open the file: `open output/matchweek-$ARGUMENTS/totw-diagram.png`

If the diagram looks wrong (e.g., blank pitch, missing badges), check:
- Badge URLs are accessible (API-Football CDN)
- Formation coordinates are correct for the selected formation
- Playwright browser is installed: `playwright install chromium`

## Diagram Requirements

The output PNG must show:
- ✅ Green football pitch background with white pitch markings
- ✅ Team badge (80×80px) at each position on the pitch
- ✅ Player name below each badge (white text on dark pill background)
- ✅ Nationality flag (24×18px) to the left of each player name
- ✅ Horizontal connector lines between players in the same positional line
- ✅ Pitch dimensions: 1200×800px
- ✅ Formation positions accurately reflect the chosen formation layout

## Output

```
Diagram generated: output/matchweek-{N}/totw-diagram.png
Size: {W}×{H}px, {filesize}KB
Formation: {N-N-N}
Players rendered: 11/11
```
