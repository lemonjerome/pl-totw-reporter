---
name: gdrive
description: Upload TOTW outputs to Google Drive and update the season GSheet with player stats. Run after /presentation. Usage: /gdrive [matchweek_number]
---

# GDrive — Upload Outputs & Update Season Stats Sheet

Upload matchweek $ARGUMENTS outputs to Google Drive and log player stats to the season GSheet.

## How It Works

All Drive uploads, folder creation, and GSheet updates are handled by a single Python script:

```bash
python3 scripts/gdrive_uploader.py $ARGUMENTS
```

This script:
- Finds or creates `My Drive/EPL TOTW Reporter/2025-26/matchweek-{NN}/` (zero-padded)
- Deletes old versions and uploads 5 fresh files: `totw_diagram.png`, `presentation.pdf`, `presentation.pptx`, `players.json`, `formation.json`
- Finds or creates the `TOTW Stats 2025-26` GSheet in the `2025-26` folder
- Ensures a `Matchweek $ARGUMENTS` tab exists and writes the 11-player stats table (header + 11 rows to A1:X12)

## Prerequisites

Verify outputs exist first:
```bash
ls output/matchweek-$ARGUMENTS/totw_diagram.png
ls output/matchweek-$ARGUMENTS/presentation.pdf
ls output/matchweek-$ARGUMENTS/presentation.pptx
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/analysis/formation.json
```

## Output Confirmation

```
GDrive upload complete ✅  Matchweek {N}

Drive: My Drive/EPL TOTW Reporter/2025-26/matchweek-{NN}/
  ✅ totw_diagram.png
  ✅ presentation.pdf
  ✅ presentation.pptx
  ✅ players.json
  ✅ formation.json

GSheet: TOTW Stats 2025-26
  Tab:          Matchweek {N}
  Rows written: 11 players (+ header)
```

## GDrive MCP Tools (read/search only)

The `gdrive` MCP server (`@isaacphi/mcp-gdrive`) is available for **reading** Drive content:
- `gdrive_search` — search for files/folders by name or query
- `gdrive_read_file` — read file contents (Sheets → CSV, Docs → Markdown)
- `gsheets_read` — read spreadsheet ranges
- `gsheets_update_cell` — update a single cell

**File uploads, deletes, and batch Sheets writes are not available via MCP** — always use `scripts/gdrive_uploader.py` for those operations.

## Auth Setup (one-time)

The Python script uses OAuth credentials from `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` (already in `settings.local.json`) and caches the token at `~/.config/pl-totw/drive_token.json`.

For the `gdrive` MCP server (read-only tools), first-time setup:
1. Place `gcp-oauth.keys.json` in `~/.config/mcp-gdrive/`
2. Add `GDRIVE_CREDS_DIR=/Users/gabrielramos/.config/mcp-gdrive` to `settings.local.json`
3. On first MCP tool call, a browser window opens for OAuth consent
