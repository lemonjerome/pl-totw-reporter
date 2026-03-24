---
name: presentation
description: Create a PL-styled Google Slides presentation for the TOTW and export to PDF. Includes results, team diagram, formation report, player slides, and next fixtures. Run after /visualize. Usage: /presentation [matchweek_number]
---

# Presentation — Google Slides TOTW Report

Create the TOTW presentation for matchweek $ARGUMENTS using Google Workspace MCP.

## Prerequisites

Verify required files exist:
```bash
ls output/matchweek-$ARGUMENTS/totw-diagram.png
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/analysis/formation_report.md
```

Verify Google Workspace MCP is connected:
- Check `/mcp` — `google-workspace` server should be listed and connected.

## Step 1: Load All Content

Read these files to prepare slide content:
- `output/matchweek-$ARGUMENTS/analysis/formation.json` — formation name and rationale
- `output/matchweek-$ARGUMENTS/analysis/players.json` — 11 players with stats
- `output/matchweek-$ARGUMENTS/analysis/formation_report.md` — formation explanation text
- `output/matchweek-$ARGUMENTS/analysis/player_reports/*.md` — per-player reports
- `data/2025-26/matchweek-$ARGUMENTS/fixtures.json` — all match results with scores
- `output/matchweek-$ARGUMENTS/totw-diagram.png` — team diagram image

Also fetch next matchweek fixtures:
```bash
python scripts/api_football.py fetch-round {N+1}
```

## Step 2: Create Presentation

Use Google Workspace MCP to create a new presentation titled: `PL TOTW Matchweek {N}`.

**Slide sequence** (follow PL design system from pl-design.md):

### Slide 1 — Title
- Background: `#37003c` (deep purple) gradient
- Title: "Premier League" (white, 48px, bold)
- Subtitle: "Team of the Week — Matchweek {N}" (green `#00ff87`, 28px)
- Season label: "2025/26" (white, 16px)

### Slide 2 — [Section] Results
- Background: `#e90052` (magenta)
- Title: "Matchweek {N} Results" (white, centered, 36px bold)

### Slide 3 — Fixtures & Results
- Background: `#37003c`
- Title: "Matchweek {N} Results" (white, 24px)
- List all 10 matches:
  - Row: [Home badge 32px] [Home team] [Score in green] [Away team] [Away badge 32px]
  - Home team on LEFT, Away team on RIGHT
  - Score in `#00ff87`, bold
  - Alternating row backgrounds: `rgba(255,255,255,0.05)`

### Slide 4 — [Section] Team of the Week
- Background: `#37003c`
- Title: "Team of the Week" (white, centered, 36px bold)
- Subtitle: "Matchweek {N} — {Formation}" (green `#00ff87`, 20px)

### Slide 5 — TOTW Diagram
- Background: Green pitch (`#1a7f37`)
- Embed `output/matchweek-{N}/totw-diagram.png` filling the slide
- Small title overlay at top: "Team of the Week — Matchweek {N}" (white, semi-transparent background)

### Slide 6 — Formation Report
- Background: `#37003c`
- Title: "Formation: {N-N-N}" (white, 28px)
- Body: Text from `formation_report.md` (white, 14px, line-height 1.6)
- Highlight key stat: e.g., "{X} teams won using this formation"

### Slide 7 — [Section] Players
- Background: `#e90052`
- Title: "The Players" (white, centered, 36px bold)

### Slides 8-18 — Individual Player Slides (1 per player)

For each of the 11 players:
- Background: `#37003c`
- **Left half**: Player image (`https://media.api-sports.io/football/players/{player_id}.png`)
  - If image unavailable: show team badge instead (full left half)
- **Right half**:
  - Position label (small, grey, uppercase, e.g., "GOALKEEPER")
  - Player name (white, 32px, bold)
  - Team badge (32px) + Club name (white, 16px)
  - Country flag (24px) + Nationality (white, 14px)
  - Stats block (top 3-4 stats):
    - Label (grey, 12px uppercase) | Value (`#00ff87`, 20px bold)
  - Selection reason (white, 12px, italic, 2-3 sentences max)

### Slide 19 — [Section] Next Week
- Background: `#37003c`
- Title: "Coming Up Next" (white, 36px bold)

### Slide 20 — Next Matchweek Fixtures
- Background: `#37003c`
- Title: "Matchweek {N+1} Fixtures" (green `#00ff87`, 24px)
- List all scheduled fixtures:
  - [Home team] vs [Away team] — [Date], [Time]
  - If season is over: "End of Season — Thank you for following the PL TOTW!"

## Step 3: Export to PDF

Use Google Workspace MCP to export the presentation to PDF format.
Download to: `output/matchweek-{N}/totw-presentation.pdf`

## Step 4: Delete from Drive

After confirming the PDF download is complete, delete the presentation from Google Drive.
This keeps Drive clean — only the local PDF copy is kept.

## Output Confirmation

```
Presentation complete for Matchweek {N}:
✅ Slides created: {total_slides} slides
✅ PDF exported: output/matchweek-{N}/totw-presentation.pdf ({filesize}MB)
✅ Presentation deleted from Google Drive
```
