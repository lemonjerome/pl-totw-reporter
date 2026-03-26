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

## Step 1: Parse the Request

Extract the matchweek number from the user's message:
- Explicit: "matchweek 30", "matchday 20", "MW30", "gameweek 15"
- If no matchweek is specified, run:
  ```bash
  python3 scripts/soccerdata_client.py check-status 31
  ```
  And step down until you find the most recently completed matchweek.

## Step 2: Check Matchweek Status

```bash
python3 scripts/soccerdata_client.py check-status {N}
```

### If COMPLETE (all FT/AET/PEN):
Proceed to Step 3.

### If INCOMPLETE (some matches still to play):
```
⚠️ Matchweek {N} is not yet complete.

✅ Completed ({X} of 10):
- [List completed matches with scores]

⏳ Still to play:
- [List pending matches with scheduled times]

Would you like the TOTW for the previous matchweek (Matchweek {N-1}) instead?
```
Stop and wait for user response.

### If FUTURE (all NS):
```
📅 Matchweek {N} hasn't started yet. It begins on {date}.
Would you like the TOTW for the most recently completed matchweek instead?
```
Stop and wait for user response.

## Step 3: Research Phase — 3 Parallel Fetcher Agents

**3a. Fetch fixtures (sequential, fast):**
```bash
python3 scripts/soccerdata_client.py fetch-round {N}
```

Read `data/2025-26/matchweek-{N}/fixtures.json` and extract all fixture IDs.

**3b. Split into 3 equal groups** using floor division + remainder:
- base = N // 3, remainder = N % 3
- Agent 1 gets base + (1 if remainder >= 1 else 0)
- Agent 2 gets base + (1 if remainder >= 2 else 0)
- Agent 3 gets base
(e.g. N=10 → 4/3/3; N=9 → 3/3/3; N=8 → 3/3/2)

**3c. Spawn all 3 `researcher-fetcher` agents in a SINGLE message (parallel):**

Agent 1 prompt: `Matchweek: {N}. Your fixture IDs: {id1} {id2} {id3} {id4} — run fetch-players-subset and fetch-lineups-subset for these IDs from /Users/gabrielramos/Desktop/PL-team-builder`

Agent 2 prompt: `Matchweek: {N}. Your fixture IDs: {id5} {id6} {id7} — run fetch-players-subset and fetch-lineups-subset for these IDs from /Users/gabrielramos/Desktop/PL-team-builder`

Agent 3 prompt: `Matchweek: {N}. Your fixture IDs: {id8} {id9} {id10} — run fetch-players-subset and fetch-lineups-subset for these IDs from /Users/gabrielramos/Desktop/PL-team-builder`

Wait for all 3 to complete.

## Step 4: Analysis Phase — Single Researcher Agent

Delegate to the **researcher** agent:

"Analyze matchweek {N} data:
1. `python3 scripts/formation_analyzer.py {N}` — select best formation
2. `python3 scripts/player_evaluator.py {N}` — select top players per position
3. `python3 scripts/report_generator.py {N}` — generate synthesis reports

Confirm formation selected and list the 11 players chosen."

After the researcher reports back, display to the user:
```
🏆 Premier League Team of the Week — Matchweek {N}

Formation: {formation}

GK: {name} ({Club})
RB: {name} ({Club})
CB: {name} ({Club})
CB: {name} ({Club})
LB: {name} ({Club})
CDM: {name} ({Club})
CM: {name} ({Club})
CM: {name} ({Club})
RW: {name} ({Club})
ST: {name} ({Club})
LW: {name} ({Club})
```

## Step 5: Visualization Phase — Single Visualizer Agent

Delegate to the **visualizer** agent:

"Generate the TOTW team diagram for matchweek {N}:
`python3 scripts/diagram_renderer.py {N}`

Confirm the PNG was created at `output/matchweek-{N}/totw_diagram.png`."

## Step 6: Presentation Phase

Delegate to the **visualizer** agent:

"Create the Google Slides presentation for matchweek {N}. Use the Google Workspace MCP to build all slides following the sequence in visualizer.md. Export to PDF at `output/matchweek-{N}/totw-presentation.pdf` and delete from Google Drive."

## Step 7: Email Delivery Phase

Delegate to the **visualizer** agent:

"Send the TOTW email for matchweek {N}:
1. `python3 scripts/compose_email.py {N}` — generate email HTML
2. Use Gmail MCP to send: from 24hrnts@gmail.com to 20gabramos04@gmail.com
3. Attach `output/matchweek-{N}/totw-presentation.pdf`"

## Step 8: Confirmation

```
✅ Premier League TOTW — Matchweek {N} Complete!

📊 Team: {Formation} — {list key players briefly}
🖼️  Diagram: output/matchweek-{N}/totw_diagram.png
📑 Slides: output/matchweek-{N}/totw-presentation.pdf
📧 Email sent to 20gabramos04@gmail.com
```
