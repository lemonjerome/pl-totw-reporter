"""
Send the TOTW email using the Gmail API with OAuth2.

Uses GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET from the environment,
plus GOOGLE_WORKSPACE_REFRESH_TOKEN if available.

If no refresh token is available, performs the interactive OAuth flow to obtain one
and saves it to ~/.config/pl-totw/gmail_token.json for future use.

Usage:
    python3 scripts/send_email_gmail.py <matchweek>
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = Path.home() / ".config" / "pl-totw" / "gmail_token.json"


def _get_credentials():
    """Return valid Gmail OAuth credentials, refreshing or re-authorizing as needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_WORKSPACE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_WORKSPACE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_WORKSPACE_REFRESH_TOKEN")

    if not client_id or not client_secret:
        raise ValueError(
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in the environment."
        )

    # 1. Try env refresh token first
    if refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds

    # 2. Try saved token file
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

    # 3. Interactive OAuth flow
    from google_auth_oauthlib.flow import InstalledAppFlow

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
    return creds


def _save_token(creds):
    """Persist credentials to TOKEN_PATH."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or SCOPES),
            }
        )
    )


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------


def _build_message(matchweek: int) -> bytes:
    """Build the MIME email message with HTML body and PDF attachment."""
    output_dir = Path(__file__).parent.parent / "output" / f"matchweek-{matchweek}"
    html_path = output_dir / "email.html"
    pdf_path = output_dir / "presentation.pdf"

    if not html_path.exists():
        raise FileNotFoundError(f"Email HTML not found: {html_path}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    html_body = html_path.read_text(encoding="utf-8")

    msg = MIMEMultipart("mixed")
    msg["To"] = "24hrnts@gmail.com"
    msg["Subject"] = f"\u26bd PL TOTW \u2014 Matchweek {matchweek}"

    # HTML body
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # PDF attachment
    pdf_bytes = pdf_path.read_bytes()
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"PL-TOTW-Matchweek-{matchweek}.pdf",
    )
    msg.attach(attachment)

    return msg.as_bytes()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/send_email_gmail.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"\nSending TOTW email for matchweek {matchweek}...")

    # Build credentials
    print("  Authenticating with Gmail API...")
    creds = _get_credentials()

    # Build message
    print("  Building MIME message...")
    raw_bytes = _build_message(matchweek)
    raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode()

    # Send via Gmail API
    print("  Sending via Gmail API...")
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=creds)
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw_b64},
    ).execute()

    msg_id = result.get("id", "unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\nEmail sent")
    print(f"  From:       24hrnts@gmail.com")
    print(f"  To:         24hrnts@gmail.com")
    print(f"  Subject:    \u26bd PL TOTW \u2014 Matchweek {matchweek}")
    print(f"  Attachment: PL-TOTW-Matchweek-{matchweek}.pdf")
    print(f"  Message ID: {msg_id}")
    print(f"  Timestamp:  {timestamp}")


if __name__ == "__main__":
    main()
