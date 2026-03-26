---
name: gdrive
description: Upload TOTW outputs to Google Drive and update the season GSheet with player stats. Run after /presentation. Requires Drive + Sheets scopes in google-workspace-mcp (see .claude/rules/gdrive.md for setup). Usage: /gdrive [matchweek_number]
---

# GDrive — Upload Outputs & Update Season Stats Sheet

Upload matchweek $ARGUMENTS outputs to Google Drive and log player stats to the season GSheet.

## Prerequisites

Verify outputs exist:
```bash
ls output/matchweek-$ARGUMENTS/totw_diagram.png
ls output/matchweek-$ARGUMENTS/presentation.pdf
ls output/matchweek-$ARGUMENTS/presentation.pptx
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/analysis/formation.json
```

If Drive or Sheets MCP tools are unavailable, ask the user to complete the one-time setup in `.claude/rules/gdrive.md`.

---

## Step 1: Resolve Drive Folder Tree

Use Drive MCP tools to navigate and create the folder structure:

```
My Drive/
  EPL TOTW Reporter/
    2025-26/
      matchweek-{NN}/     ← zero-padded, e.g. matchweek-23
```

1. List files/folders in My Drive root. Find `EPL TOTW Reporter`. If absent, create it.
2. Inside `EPL TOTW Reporter`, find `2025-26`. If absent, create it.
3. Inside `2025-26`, find `matchweek-{NN}` (zero-pad: `f"matchweek-{N:02d}"`). If absent, create it.

Record the **matchweek folder ID** — needed for all uploads.

---

## Step 2: Upload Files

Upload these 5 files to the matchweek folder. For each file:
1. Check if a file with the same name already exists (use `gdrive_list_files` or equivalent).
2. If it exists, delete it first to avoid duplicates.
3. Upload the new version.

| Local path | Drive filename |
|---|---|
| `output/matchweek-$ARGUMENTS/totw_diagram.png` | `totw_diagram.png` |
| `output/matchweek-$ARGUMENTS/presentation.pdf` | `presentation.pdf` |
| `output/matchweek-$ARGUMENTS/presentation.pptx` | `presentation.pptx` |
| `output/matchweek-$ARGUMENTS/analysis/players.json` | `players.json` |
| `output/matchweek-$ARGUMENTS/analysis/formation.json` | `formation.json` |

---

## Step 3: Locate or Create the Season GSheet

In the `2025-26` folder, look for a file named exactly **`TOTW Stats 2025-26`** (Google Sheets type).

- **If found**: get its spreadsheet ID.
- **If not found**: create a new spreadsheet named `TOTW Stats 2025-26` using Sheets MCP (`gsheets_create_spreadsheet` or equivalent), then move it to the `2025-26` Drive folder.

Record the **spreadsheet ID**.

---

## Step 4: Ensure the Matchweek Tab Exists

In the spreadsheet, look for a sheet (tab) named **`Matchweek $ARGUMENTS`** (not zero-padded).

- **If absent**: add it with `gsheets_add_sheet` or `gsheets_batch_update`.
- **If present**: clear it (delete rows 2+ or use `gsheets_clear_values` for range `A2:X12`).

---

## Step 5: Read players.json

Read `output/matchweek-$ARGUMENTS/analysis/players.json`.

The file has a `"players"` list of 11 entries. For each entry, extract the 24 column values in this order:

```
position_slot | player.name | player.team_name | player.country_code |
player.specific_position | player.stats.games.minutes | player.stats.games.rating |
player.stats.goals.total | player.stats.goals.assists | player.stats.passes.key |
player.stats.shots.on | player.stats.shots.total | player.stats.goals.saves |
player.stats.goals.conceded | player.stats.tackles.total | player.stats.tackles.interceptions |
player.stats.tackles.clearances | player.stats.tackles.blocks | player.stats.duels.won |
player.stats.duels.aerial_won | player.stats.passes.accuracy | player.stats.dribbles.success |
key_stat | player.fixture_result
```

Convert `null`/`None` → `""`. Use values as-is (no rounding).

Build **12 rows** total:
- **Row 1**: header — the 24 column names listed in `.claude/rules/gdrive.md`
- **Rows 2–12**: one row per player in the order they appear in `players.json` (GK first)

---

## Step 6: Write to GSheet

Write all 12 rows to range `A1:X12` in the `Matchweek $ARGUMENTS` tab using `gsheets_update_values` (or equivalent Sheets MCP tool).

Set `valueInputOption` to `RAW` (not `USER_ENTERED`) so numbers stay as numbers.

---

## Step 7: Confirm

Print:

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
