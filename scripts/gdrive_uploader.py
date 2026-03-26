"""
Upload matchweek TOTW outputs to Google Drive and log player stats to the season GSheet.

Folder structure created/reused:
  My Drive/
    EPL TOTW Reporter/
      2025-26/
        matchweek-NN/      (zero-padded)
          totw_diagram.png
          presentation.pdf
          presentation.pptx
          players.json
          formation.json

GSheet: "TOTW Stats 2025-26" in the 2025-26 folder.
  Tab: "Matchweek N" (not zero-padded)
  Range A1:X12  (header row + 11 players)

Usage:
    python3 scripts/gdrive_uploader.py <matchweek>

Auth:
    Uses GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET from env.
    Token saved to ~/.config/pl-totw/drive_token.json.
    On first run, opens a browser for OAuth consent (Drive + Sheets scopes).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
TOKEN_PATH = Path.home() / ".config" / "pl-totw" / "drive_token.json"
DRIVE_ROOT_FOLDER = "EPL TOTW Reporter"
SEASON_FOLDER = "2025-26"
GSHEET_NAME = "TOTW Stats 2025-26"

HEADER = [
    "Position Slot", "Player", "Team", "Nationality", "Specific Position",
    "Minutes", "Rating", "Goals", "Assists", "Key Passes",
    "Shots On Target", "Total Shots", "Saves", "Goals Conceded",
    "Tackles Won", "Interceptions", "Clearances", "Blocks",
    "Duels Won", "Aerial Won", "Pass Accuracy", "Dribbles",
    "Key Stat", "Fixture Result",
]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_credentials():
    """Return valid Drive+Sheets credentials, refreshing or re-authorizing as needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_WORKSPACE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_WORKSPACE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set."
        )

    # Try saved token
    if TOKEN_PATH.exists():
        data = json.loads(TOKEN_PATH.read_text())
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        return creds

    # Interactive OAuth flow
    from google_auth_oauthlib.flow import InstalledAppFlow

    print("\nNo Drive/Sheets token found. Opening browser for OAuth consent...")
    print("Please grant access to Google Drive and Google Sheets.\n")
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    print(f"Token saved to {TOKEN_PATH}\n")
    return creds


def _save_token(creds):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }))


# ---------------------------------------------------------------------------
# Drive helpers
# ---------------------------------------------------------------------------

def _find_folder(service, name: str, parent_id: str | None = None) -> str | None:
    """Return the Drive folder ID for `name` inside `parent_id`, or None."""
    q = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    resp = service.files().list(q=q, fields="files(id,name)", spaces="drive").execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str | None = None) -> str:
    """Create a Drive folder and return its ID."""
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    f = service.files().create(body=meta, fields="id").execute()
    return f["id"]


def _find_or_create_folder(service, name: str, parent_id: str | None = None) -> tuple[str, bool]:
    """Return (folder_id, created). Creates folder if it doesn't exist."""
    fid = _find_folder(service, name, parent_id)
    if fid:
        return fid, False
    fid = _create_folder(service, name, parent_id)
    return fid, True


def _find_file_in_folder(service, name: str, folder_id: str) -> str | None:
    """Return file ID if `name` exists in `folder_id`, else None."""
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    resp = service.files().list(q=q, fields="files(id,name)").execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _delete_file(service, file_id: str) -> None:
    service.files().delete(fileId=file_id).execute()


def _upload_file(service, local_path: Path, filename: str, folder_id: str, mime_type: str) -> str:
    """Upload local_path to Drive folder as filename. Returns the new file ID."""
    from googleapiclient.http import MediaFileUpload

    meta = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    f = service.files().create(body=meta, media_body=media, fields="id").execute()
    return f["id"]


MIME_MAP = {
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".json": "application/json",
}


# ---------------------------------------------------------------------------
# Sheets helpers
# ---------------------------------------------------------------------------

def _find_sheet(drive_service, name: str, parent_id: str) -> str | None:
    """Return spreadsheet ID if a Google Sheet named `name` exists in folder."""
    q = (
        f"mimeType='application/vnd.google-apps.spreadsheet' "
        f"and name='{name}' and '{parent_id}' in parents and trashed=false"
    )
    resp = drive_service.files().list(q=q, fields="files(id,name)").execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _create_sheet(sheets_service, drive_service, name: str, folder_id: str) -> str:
    """Create a new spreadsheet named `name`, move it to `folder_id`, return its ID."""
    ss = sheets_service.spreadsheets().create(
        body={"properties": {"title": name}}, fields="spreadsheetId"
    ).execute()
    ss_id = ss["spreadsheetId"]

    # Move to the target folder
    f = drive_service.files().get(fileId=ss_id, fields="parents").execute()
    previous_parents = ",".join(f.get("parents", []))
    drive_service.files().update(
        fileId=ss_id,
        addParents=folder_id,
        removeParents=previous_parents,
        fields="id,parents",
    ).execute()
    return ss_id


def _get_sheet_tabs(sheets_service, ss_id: str) -> list[dict]:
    meta = sheets_service.spreadsheets().get(spreadsheetId=ss_id, fields="sheets.properties").execute()
    return meta.get("sheets", [])


def _add_tab(sheets_service, ss_id: str, tab_name: str) -> None:
    body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
    sheets_service.spreadsheets().batchUpdate(spreadsheetId=ss_id, body=body).execute()


def _clear_range(sheets_service, ss_id: str, tab_name: str, range_a1: str) -> None:
    full_range = f"'{tab_name}'!{range_a1}"
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=ss_id, range=full_range, body={}
    ).execute()


def _write_values(sheets_service, ss_id: str, tab_name: str, values: list[list]) -> None:
    full_range = f"'{tab_name}'!A1:X12"
    sheets_service.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range=full_range,
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


# ---------------------------------------------------------------------------
# Player data extraction
# ---------------------------------------------------------------------------

def _null(val):
    return "" if val is None else val


def extract_player_rows(players_json_path: Path) -> list[list]:
    """Return [header_row] + [11 player rows] from players.json."""
    data = json.loads(players_json_path.read_text())
    rows = [HEADER]
    for entry in data["players"]:
        p = entry["player"]
        s = p["stats"]
        row = [
            _null(entry.get("position_slot")),
            _null(p.get("name")),
            _null(p.get("team_name")),
            _null(p.get("country_code")),
            _null(p.get("specific_position")),
            _null(s["games"].get("minutes")),
            _null(s["games"].get("rating")),
            _null(s["goals"].get("total")),
            _null(s["goals"].get("assists")),
            _null(s["passes"].get("key")),
            _null(s["shots"].get("on")),
            _null(s["shots"].get("total")),
            _null(s["goals"].get("saves")),
            _null(s["goals"].get("conceded")),
            _null(s["tackles"].get("total")),
            _null(s["tackles"].get("interceptions")),
            _null(s["tackles"].get("clearances")),
            _null(s["tackles"].get("blocks")),
            _null(s["duels"].get("won")),
            _null(s["duels"].get("aerial_won")),
            _null(s["passes"].get("accuracy")),
            _null(s["dribbles"].get("success")),
            _null(entry.get("key_stat")),
            _null(p.get("fixture_result")),
        ]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/gdrive_uploader.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    mw_folder_name = f"matchweek-{matchweek:02d}"
    tab_name = f"Matchweek {matchweek}"

    project_root = Path(__file__).parent.parent
    output_dir = project_root / "output" / f"matchweek-{matchweek}"

    files_to_upload = [
        (output_dir / "totw_diagram.png", "totw_diagram.png"),
        (output_dir / "presentation.pdf", "presentation.pdf"),
        (output_dir / "presentation.pptx", "presentation.pptx"),
        (output_dir / "analysis" / "players.json", "players.json"),
        (output_dir / "analysis" / "formation.json", "formation.json"),
    ]

    print(f"\nMatchweek {matchweek} — Google Drive upload starting...")

    # Verify local files
    for local_path, _ in files_to_upload:
        if not local_path.exists():
            print(f"ERROR: Missing required file: {local_path}")
            sys.exit(1)
    print("  All local files verified.")

    # Auth
    print("  Authenticating...")
    creds = get_credentials()

    from googleapiclient.discovery import build

    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)
    print("  Services initialized.\n")

    # --- Step 1: Resolve Drive folder tree ---
    print("Step 1: Resolving Drive folder tree...")

    root_id, created = _find_or_create_folder(drive, DRIVE_ROOT_FOLDER)
    print(f"  {'Created' if created else 'Found'} folder: {DRIVE_ROOT_FOLDER} (id={root_id})")

    season_id, created = _find_or_create_folder(drive, SEASON_FOLDER, root_id)
    print(f"  {'Created' if created else 'Found'} folder: {SEASON_FOLDER} (id={season_id})")

    mw_id, created = _find_or_create_folder(drive, mw_folder_name, season_id)
    print(f"  {'Created' if created else 'Found'} folder: {mw_folder_name} (id={mw_id})")

    # --- Step 2: Upload files ---
    print(f"\nStep 2: Uploading 5 files to {mw_folder_name}...")
    uploaded = []
    for local_path, drive_name in files_to_upload:
        existing_id = _find_file_in_folder(drive, drive_name, mw_id)
        if existing_id:
            _delete_file(drive, existing_id)
            print(f"  Deleted existing: {drive_name}")
        mime = MIME_MAP.get(local_path.suffix, "application/octet-stream")
        _upload_file(drive, local_path, drive_name, mw_id, mime)
        print(f"  Uploaded: {drive_name} ({local_path.stat().st_size // 1024} KB)")
        uploaded.append(drive_name)

    # --- Step 3: Locate or create GSheet ---
    print(f"\nStep 3: Locating GSheet '{GSHEET_NAME}'...")
    ss_id = _find_sheet(drive, GSHEET_NAME, season_id)
    if ss_id:
        print(f"  Found existing GSheet (id={ss_id})")
    else:
        ss_id = _create_sheet(sheets, drive, GSHEET_NAME, season_id)
        print(f"  Created new GSheet (id={ss_id})")

    # --- Step 4: Ensure tab exists ---
    print(f"\nStep 4: Ensuring tab '{tab_name}' exists...")
    tabs = _get_sheet_tabs(sheets, ss_id)
    tab_names = [t["properties"]["title"] for t in tabs]
    if tab_name in tab_names:
        print(f"  Tab found — clearing A2:X12...")
        _clear_range(sheets, ss_id, tab_name, "A2:X12")
    else:
        print(f"  Tab not found — creating '{tab_name}'...")
        _add_tab(sheets, ss_id, tab_name)

    # --- Step 5: Extract player data ---
    print(f"\nStep 5: Extracting player data from players.json...")
    rows = extract_player_rows(output_dir / "analysis" / "players.json")
    print(f"  Extracted {len(rows) - 1} players + 1 header = {len(rows)} rows.")

    # --- Step 6: Write to GSheet ---
    print(f"\nStep 6: Writing {len(rows)} rows to '{tab_name}'!A1:X12...")
    _write_values(sheets, ss_id, tab_name, rows)
    print("  Write complete.")

    # --- Step 7: Confirm ---
    print(f"""
GDrive upload complete   Matchweek {matchweek}

Drive: My Drive/{DRIVE_ROOT_FOLDER}/{SEASON_FOLDER}/{mw_folder_name}/
  OK totw_diagram.png
  OK presentation.pdf
  OK presentation.pptx
  OK players.json
  OK formation.json

GSheet: {GSHEET_NAME}
  Tab:          {tab_name}
  Rows written: {len(rows) - 1} players (+ header)
""")


if __name__ == "__main__":
    main()
