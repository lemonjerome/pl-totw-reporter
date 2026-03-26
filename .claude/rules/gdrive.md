# Google Drive & Sheets — Integration Rules

Rules for storing EPL TOTW outputs in Google Drive and logging season stats to a GSheet.

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
This ensures correct lexicographic sort order in Drive.

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

## GDrive-First Cache Rule (Research Skill)

Before fetching any data from SofaScore/FPL, the research skill checks GDrive for cached analysis outputs.

**Algorithm (Step 0 of /research)**:
1. Use Drive MCP to navigate to `EPL TOTW Reporter / 2025-26 / matchweek-{NN}/`.
2. List files in that folder.
3. Check whether **both** `players.json` **and** `formation.json` are present.

**Cache HIT** (both files exist):
- Download `players.json` → `output/matchweek-N/analysis/players.json`
- Download `formation.json` → `output/matchweek-N/analysis/formation.json`
- Print: `GDrive cache hit ✅ Matchweek N — skipping fetch pipeline`
- Jump directly to Step 7 (verify).

**Cache MISS** (either file absent):
- Print: `GDrive cache miss — running full fetch pipeline.`
- Continue with Step 1 (fixture status check).

**Drive unavailable** (MCP not connected / auth error):
- Print a warning and continue with Step 1. Never block the pipeline.

---

## File Overwrite Policy

When uploading to Drive, always check if a file with the same name exists in the target folder and **delete the old version before uploading**. This prevents duplicate files accumulating in Drive.

---

## Authentication Setup (one-time)

The `google-workspace-mcp` server in `.mcp.json` handles Gmail, Drive, and Sheets. Gmail is already authorized. Drive and Sheets require additional OAuth scopes.

### Step 1 — Enable APIs
1. Go to [Google Cloud Console](https://console.cloud.google.com) → your project.
2. **APIs & Services → Library** → enable:
   - **Google Drive API**
   - **Google Sheets API**

### Step 2 — Add OAuth Scopes
1. **APIs & Services → OAuth consent screen → Edit App → Scopes**.
2. Add:
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/spreadsheets`
3. Save.

### Step 3 — Delete Existing Token
The current token was issued only for Gmail. Delete it so the MCP re-authenticates with expanded scopes:
```bash
find ~ -name "*google*token*" 2>/dev/null
# Delete the token file found, e.g.:
rm ~/.config/google-workspace-mcp/token.json
```

### Step 4 — Re-authorize
Restart Claude Code. On first use of a Drive or Sheets MCP tool, a browser window will open for consent. Approve all requested scopes.

---

## Common Errors

| Error | Fix |
|-------|-----|
| "insufficient permission" on Drive/Sheets | Add Drive/Sheets scopes and re-authenticate (Step 2–4 above) |
| Folder not found | Agent must create it — absence is not an error |
| players.json not in Drive | GDrive cache miss — run full research pipeline |
| Spreadsheet not found | Agent creates it on first use — not an error |
| Duplicate files in folder | Delete old file before uploading (see overwrite policy) |
