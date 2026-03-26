---
name: email
description: Send the TOTW email via Gmail MCP (send_email tool). PL-styled HTML email with inline diagram, results table, TOTW XI, and PDF attachment. Self-sent from/to your-email@gmail.com. Run after /presentation. Usage: /email [matchweek_number]
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

This script renders `templates/email.html` with all matchweek data and embeds the diagram as a base64 inline image. It saves the result to `output/matchweek-$ARGUMENTS/email.html` and prints a send summary.

If the script fails, read the error and fix before continuing.

## Step 2: Send via Python Gmail Script

The email HTML embeds the diagram as a base64 inline image (~1.5 MB), which is too large for the Gmail MCP tool. Always use the Python script:

```bash
python3 scripts/send_email_gmail.py $ARGUMENTS
```

## Step 4: Confirm Delivery

After the send call succeeds, print:

```
Email sent ✅
  From:       your-email@gmail.com
  To:         your-email@gmail.com
  Subject:    ⚽ PL TOTW — Matchweek $ARGUMENTS
  Attachment: PL-TOTW-Matchweek-$ARGUMENTS.pdf
  Timestamp:  {datetime}
```

## Auth Setup (one-time)

If the Gmail MCP has never been authorized on this machine:
```bash
npx @gongrzhe/server-gmail-autoauth-mcp auth
```
This opens a browser OAuth consent flow. Token is stored in `~/.gmail-mcp/` and reused automatically on all subsequent sessions.
