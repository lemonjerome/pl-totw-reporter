"""
Email Sender for EPL TOTW.

Prepares the PL-styled HTML email body and saves it to:
  output/matchweek-{N}/email.html

Does NOT send the email — sending is done by the /email skill via Gmail MCP.

Usage:
    python3 scripts/email_sender.py <matchweek>

Output:
    output/matchweek-{N}/email.html
    Prints a summary: subject, from/to, HTML path, attachment path + size.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jinja2 import Environment, FileSystemLoader

from scripts.presentation_builder import _diagram_data_uri, load_presentation_data
from scripts.utils import matchweek_output_dir

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
PROJECT_EMAIL = os.environ.get("PROJECT_EMAIL", "you@gmail.com")


def build_email(matchweek: int) -> Path:
    """Render email HTML and save to output/matchweek-{N}/email.html."""
    print(f"\nBuilding email for matchweek {matchweek}...")

    # Load all presentation data (fixtures, players, formation, rationale)
    data = load_presentation_data(matchweek)

    # Embed diagram as base64 data URI (reuse existing helper)
    diagram_uri = _diagram_data_uri(matchweek)
    if diagram_uri:
        size_kb = len(diagram_uri) * 3 // 4 // 1024  # approx decoded bytes
        print(f"  Diagram:   embedded ({size_kb} KB)")
    else:
        print("  WARNING:   totw_diagram.png not found — diagram will be omitted")

    # Slim player list down to what the email template needs
    email_players = [
        {
            "position_slot": p["position_slot"],
            "name":          p["name"],
            "team_name":     p["team_name"],
            "key_stat":      p["key_stat"],
        }
        for p in data["players"]
    ]

    template_vars = {
        "matchweek":           data["matchweek"],
        "season":              data["season"],
        "formation":           data["formation"],
        "formation_rationale": data["formation_rationale"],
        "fixtures":            data["fixtures"],
        "players":             email_players,
        "diagram_data_uri":    diagram_uri,
        "project_email":       PROJECT_EMAIL,
    }

    # Render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    template = env.get_template("email.html")
    html = template.render(**template_vars)

    # Save
    output_dir = matchweek_output_dir(matchweek)
    email_path = output_dir / "email.html"
    email_path.write_text(html, encoding="utf-8")
    size_kb = email_path.stat().st_size // 1024
    print(f"  Email HTML: {email_path} ({size_kb} KB)")

    # Print send summary for the skill agent
    pdf_path = output_dir / "presentation.pdf"
    if pdf_path.exists():
        pdf_mb = f"{pdf_path.stat().st_size / 1_048_576:.1f} MB"
    else:
        pdf_mb = "NOT FOUND — run /presentation first"

    print(f"\nReady to send:")
    print(f"  Subject:    ⚽ PL TOTW — Matchweek {matchweek}")
    print(f"  From:       {PROJECT_EMAIL}")
    print(f"  To:         {PROJECT_EMAIL}")
    print(f"  Body:       {email_path}")
    print(f"  Attachment: {pdf_path} ({pdf_mb})")
    print(f"  Rename to:  PL-TOTW-Matchweek-{matchweek}.pdf")

    return email_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/email_sender.py <matchweek>")
        sys.exit(1)
    matchweek = int(sys.argv[1])
    build_email(matchweek)


if __name__ == "__main__":
    main()
