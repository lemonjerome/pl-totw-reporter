---
name: totw
description: Build the Premier League Team of the Week. Orchestrates the full pipeline: data collection, formation/player analysis, team diagram, Google Slides presentation, and Gmail delivery. Invoke with a matchweek number or leave blank for the current matchweek.
---

# Premier League Team of the Week Builder

Build the TOTW for the specified matchweek (or auto-detect current if not specified).

**Usage**: `/totw [matchweek_number]`

Examples:
- `/totw 30` — Build TOTW for Matchweek 30
- `/totw` — Build TOTW for the latest completed matchweek
- `What is the EPL TOTW for Matchday 30?` — Also triggers this skill

## Step 1: Parse the Request

Extract the matchweek number from the user's message:
- Explicit: "matchweek 30", "matchday 20", "MW30", "gameweek 15"
- Implicit "current": detect from API
- Relative: "last week" = current matchweek - 1, "this week" = current matchweek

If no matchweek is specified, use the researcher agent to call:
```
python scripts/api_football.py get-current-round
```

## Step 2: Check Matchweek Status

Use the researcher agent to check fixture statuses:
```
python scripts/api_football.py check-status {N}
```

### If COMPLETE (all FT/AET/PEN):
Proceed to Step 3.

### If INCOMPLETE (some matches still to play):
Inform the user:
```
⚠️ Matchweek {N} is not yet complete.

✅ Completed ({X} of 10):
- [List completed matches with scores]

⏳ Still to play:
- [List pending matches with scheduled times]

Would you like the TOTW for the previous matchweek (Matchweek {N-1}) instead?
```
Stop and wait for user response.

### If FUTURE (all NS, hasn't started):
Inform the user:
```
📅 Matchweek {N} hasn't started yet.

Upcoming fixtures:
- [List all scheduled matches with dates/times]

The matchweek begins on {date}.

Would you like the TOTW for the most recently completed matchweek instead?
```
Stop and wait for user response.

## Step 3: Research Phase

Delegate to the **researcher** agent:

"Please collect all matchweek {N} data. Run the following:
1. `python scripts/api_football.py fetch-round {N}` — get all fixtures
2. `python scripts/api_football.py fetch-players {fixture_id}` — repeat for each fixture
3. `python scripts/pl_scraper.py match-reports {N}` — scrape match reports
4. `python scripts/pl_scraper.py commentaries {N}` — scrape commentaries

Verify all data is saved to `data/2025-26/matchweek-{N}/`."

## Step 4: Analysis Phase

Delegate to the **researcher** agent:

"Now analyze the matchweek {N} data:
1. `python scripts/formation_analyzer.py {N}` — select best formation
2. `python scripts/player_evaluator.py {N}` — select top players per position
3. `python scripts/report_generator.py {N}` — generate synthesis reports

Confirm what formation was selected and list the 11 players chosen."

After the researcher reports back, display the selected team to the user:
```
🏆 Premier League Team of the Week — Matchweek {N}

Formation: {formation}

11: {GK name} (GK, {Club})
2: {RB name} (RB, {Club})
...
```

## Step 5: Visualization Phase

Delegate to the **visualizer** agent:

"Generate the TOTW team diagram for matchweek {N}:
`python scripts/diagram_renderer.py {N}`

Confirm the PNG was created at `output/matchweek-{N}/totw-diagram.png`."

## Step 6: Presentation Phase

Delegate to the **visualizer** agent:

"Create the Google Slides presentation for matchweek {N}. Use the Google Workspace MCP to build all slides following the sequence in visualizer.md. Export to PDF at `output/matchweek-{N}/totw-presentation.pdf` and delete from Google Drive."

## Step 7: Email Delivery Phase

Delegate to the **visualizer** agent:

"Send the TOTW email for matchweek {N}:
1. `python scripts/compose_email.py {N}` — generate email HTML
2. Use Gmail MCP to send: from 24hrnts@gmail.com to 20gabramos04@gmail.com
3. Attach `output/matchweek-{N}/totw-presentation.pdf`"

## Step 8: Confirmation

Report back to the user:
```
✅ Premier League TOTW — Matchweek {N} Complete!

📊 Team: {Formation} — {list key players briefly}
🖼️  Diagram: output/matchweek-{N}/totw-diagram.png
📑 Slides: output/matchweek-{N}/totw-presentation.pdf
📧 Email sent to 20gabramos04@gmail.com
```
