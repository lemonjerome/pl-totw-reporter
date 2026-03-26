---
name: email
description: Send the TOTW email via Gmail MCP. PL-styled HTML email with inline diagram, results table, TOTW XI, and PDF attachment. Self-sent from/to 24hrnts@gmail.com. Run after /presentation. Usage: /email [matchweek_number]
---

# Email — Send TOTW via Gmail

Send the TOTW email for matchweek $ARGUMENTS.

## Prerequisites

Verify these files exist before running:
```bash
ls output/matchweek-$ARGUMENTS/totw_diagram.png
ls output/matchweek-$ARGUMENTS/analysis/players.json
ls output/matchweek-$ARGUMENTS/presentation.pdf
```

If any are missing, run the earlier pipeline stages first (`/research`, `/analyze`, `/visualize`, `/presentation`).

## Step 1: Generate Email HTML

```bash
python3 scripts/email_sender.py $ARGUMENTS
```

This script:
- Loads `output/matchweek-{N}/analysis/players.json` and `formation.json`
- Loads `data/2025-26/matchweek-{N}/fixtures.json` for match results
- Embeds `output/matchweek-{N}/totw_diagram.png` as a base64 inline image
- Renders `templates/email.html` with full PL branding
- Saves the result to `output/matchweek-{N}/email.html`
- Prints the send summary: subject, from, to, HTML path, attachment path

If the script fails, read the error output and fix the issue before continuing.

## Step 2: Read Email Content

Read the generated HTML:
```
output/matchweek-$ARGUMENTS/email.html
```

This is the complete HTML body. Do not modify it.

## Step 3: Send via Gmail MCP

Use Gmail MCP tools to send the email:

- **From**: `24hrnts@gmail.com`
- **To**: `24hrnts@gmail.com`
- **Subject**: `⚽ PL TOTW — Matchweek $ARGUMENTS`
- **Body**: HTML content from `output/matchweek-$ARGUMENTS/email.html`
- **Attachment**: `output/matchweek-$ARGUMENTS/presentation.pdf`
  - In the send call, name the attachment `PL-TOTW-Matchweek-$ARGUMENTS.pdf`

If Gmail MCP authentication fails, ask the user to verify OAuth credentials in Google Cloud Console.

## Step 4: Confirm Delivery

After the send call succeeds, print:

```
Email sent ✅
  From:       24hrnts@gmail.com
  To:         24hrnts@gmail.com
  Subject:    ⚽ PL TOTW — Matchweek {N}
  Attachment: PL-TOTW-Matchweek-{N}.pdf
  Timestamp:  {datetime}
```
