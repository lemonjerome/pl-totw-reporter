# Google Drive & Sheets — Integration Rules

Rules for storing EPL TOTW outputs in Google Drive and logging season stats to a GSheet.

## How Uploads Work

All Drive uploads and GSheet writes are handled by **`scripts/gdrive_uploader.py`** (Python, Google Drive API v3 + Sheets API v4). The `@isaacphi/mcp-gdrive` MCP server is read-only and cannot upload files.

```bash
python3 scripts/gdrive_uploader.py {N}
```

---

## Folder Structure

```
My Drive/
  EPL TOTW Reporter/              ← root project folder; create once if absent
    2025-26/                      ← season folder
      TOTW Stats 2025-26          ← single GSheet for the whole season
      matchweek-01/               ← zero-padded two digits: 01 … 38
        totw_diagram.png
        presentation.pdf
        presentation.pptx
        players.json              ← copy of output/matchweek-N/analysis/players.json
        formation.json            ← copy of output/matchweek-N/analysis/formation.json
      matchweek-12/
        ...
```

### Folder Naming Convention

Matchweek folders are **always zero-padded to 2 digits**: `matchweek-01` through `matchweek-38`.

```python
folder_name = f"matchweek-{matchweek:02d}"
```

GSheet tab names are **NOT padded**: `Matchweek 1`, `Matchweek 12`, `Matchweek 23`.

---

## GSheet: "TOTW Stats 2025-26"

One tab per matchweek, named `Matchweek N`.

**Row 1** — Header (24 columns):

| Col | Field |
|-----|-------|
| A | Position Slot |
| B | Player |
| C | Team |
| D | Nationality |
| E | Specific Position |
| F | Minutes |
| G | Rating |
| H | Goals |
| I | Assists |
| J | Key Passes |
| K | Shots On Target |
| L | Total Shots |
| M | Saves |
| N | Goals Conceded |
| O | Tackles Won |
| P | Interceptions |
| Q | Clearances |
| R | Blocks |
| S | Duels Won |
| T | Aerial Won |
| U | Pass Accuracy |
| V | Dribbles |
| W | Key Stat |
| X | Fixture Result |

**Rows 2–12** — One player per row, order: GK → defenders → midfielders → attackers.

Source paths from `output/matchweek-N/analysis/players.json`:
- `position_slot` → `player.name` → `player.team_name` → `player.country_code`
- `player.specific_position`
- `player.stats.games.minutes` → `player.stats.games.rating`
- `player.stats.goals.total` → `player.stats.goals.assists`
- `player.stats.passes.key` → `player.stats.shots.on` → `player.stats.shots.total`
- `player.stats.goals.saves` → `player.stats.goals.conceded`
- `player.stats.tackles.total` → `.interceptions` → `.clearances` → `.blocks`
- `player.stats.duels.won` → `player.stats.duels.aerial_won`
- `player.stats.passes.accuracy` → `player.stats.dribbles.success`
- `key_stat` → `player.fixture_result`

Use `""` for `null`/`None` values. Do not round — use raw values.

---

## File Overwrite Policy

`scripts/gdrive_uploader.py` always deletes any existing file with the same name before uploading. This prevents duplicate files accumulating in Drive.

---

## MCP Server: `@isaacphi/mcp-gdrive` (read-only)

The `gdrive` MCP server provides **read and search** tools only:

| Tool | Purpose |
|------|---------|
| `gdrive_search` | Search files/folders by name or query |
| `gdrive_read_file` | Read file contents (Sheets → CSV, Docs → Markdown) |
| `gsheets_read` | Read spreadsheet ranges |
| `gsheets_update_cell` | Update a single cell (ad-hoc only) |

**These tools cannot upload, delete, or move files.** Never use them for the upload workflow.

---

## Authentication Setup

### Python script auth (`scripts/gdrive_uploader.py`)
Uses `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` from `settings.local.json`.
Token cached at `~/.config/pl-totw/drive_token.json` — browser consent on first run only.

### GDrive MCP auth (`@isaacphi/mcp-gdrive`)
1. Download OAuth Desktop App credentials JSON from Google Cloud Console
2. Save as `~/.config/mcp-gdrive/gcp-oauth.keys.json`
3. Add to `settings.local.json`: `"GDRIVE_CREDS_DIR": "/Users/gabrielramos/.config/mcp-gdrive"`
4. On first MCP tool use, a browser opens for OAuth consent — token saved to `GDRIVE_CREDS_DIR`

---

## Common Errors

| Error | Fix |
|-------|-----|
| "insufficient permission" | Re-run Python script — it will re-authenticate |
| Folder not found | Script auto-creates it |
| Spreadsheet not found | Script auto-creates it on first use |
| Duplicate files in folder | Script deletes old file before uploading (automatic) |
