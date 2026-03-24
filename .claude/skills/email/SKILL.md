---
name: email
description: Send the TOTW email via Gmail with the team diagram image and PDF presentation attached. PL-styled HTML email with enthusiastic tone. Run after /presentation. Usage: /email [matchweek_number]
---

# Email — Send TOTW via Gmail

Send the TOTW email for matchweek $ARGUMENTS using Google Workspace MCP.

## Prerequisites

Verify required files exist:
```bash
ls output/matchweek-$ARGUMENTS/totw-presentation.pdf
ls output/matchweek-$ARGUMENTS/totw-diagram.png
ls output/matchweek-$ARGUMENTS/analysis/summary.md
```

Verify Google Workspace MCP is connected (Gmail tools available).

## Step 1: Generate Email HTML

```bash
python scripts/compose_email.py $ARGUMENTS
```

This renders `templates/email.html` with:
- Matchweek number
- Summary text from `analysis/summary.md`
- TOTW diagram embedded inline (base64)
- Formation name and key players
- CTA reference to PDF attachment

Saves to: `output/matchweek-{N}/email.html`

## Step 2: Read Email Content

Read the generated `output/matchweek-{N}/email.html` to prepare the send payload.

Also read `output/matchweek-{N}/analysis/summary.md` for the key highlights.

## Step 3: Send Email via Gmail MCP

Use Gmail MCP tools to compose and send:

- **From**: 24hrnts@gmail.com
- **To**: 20gabramos04@gmail.com
- **Subject**: `⚽ Premier League TOTW — Matchweek {N} is here!`
- **Body**: HTML content from `output/matchweek-{N}/email.html`
- **Attachment**: `output/matchweek-{N}/totw-presentation.pdf` (named `PL-TOTW-Matchweek-{N}.pdf`)

## Email Tone & Content Guidelines

The email body should be:
- **Short**: 3-4 sentences of body text maximum
- **Enthusiastic**: Football fan energy, not corporate
- **Informative**: Mention the formation and 1-2 standout players
- **PL-styled**: Matches the Premier League website visual identity

Sample subject lines (use one, vary by matchweek):
- `⚽ Premier League TOTW — Matchweek {N} is here!`
- `🏆 The Premier League Team of the Week — Matchweek {N}`
- `⚽ Who made it? Matchweek {N} TOTW revealed!`

Sample body opening (personalize):
> "What a matchweek! The goals were flying in, the saves were stunning, and {standout_player} was simply unplayable. Check out this week's Premier League Team of the Week — {formation}, packed with world-class talent."

## Step 4: Confirm Delivery

After sending, confirm:
```
Email sent ✅
  From: 24hrnts@gmail.com
  To: 20gabramos04@gmail.com
  Subject: ⚽ Premier League TOTW — Matchweek {N} is here!
  Attachment: PL-TOTW-Matchweek-{N}.pdf ({size}MB)
  Timestamp: {datetime}
```
