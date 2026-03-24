# Premier League Design System — Styling Guide

All visual outputs (team diagram, slides, email) must follow this design system to match the PL website aesthetic.

## Color Palette

| Name | Hex | Usage |
|------|-----|-------|
| Primary Purple | `#37003c` | Main backgrounds, headers, slide backgrounds |
| Secondary Purple | `#2D0032` | Gradient endpoint, secondary backgrounds |
| Accent Green | `#00ff87` | Highlights, accents, scores, selected text |
| Accent Magenta | `#e90052` | Alerts, important numbers, CTA buttons |
| White | `#FFFFFF` | Text on dark backgrounds |
| Light Grey | `#F5F5F5` | Light section backgrounds |
| Dark Grey | `#1a1a2e` | Alternative dark background |

**Gradient**: `linear-gradient(to right, #37003c, #2D0032)` — use for headers and slide backgrounds.

## Typography

The PL uses a custom font called "PremierLeague". As it's proprietary, use this font stack:
```css
font-family: "PL", "Helvetica Neue", Arial, sans-serif;
```

**Text styles**:
- **Heading 1**: Bold, 36-48px, white on purple
- **Heading 2**: Bold, 24-28px, white or green accent
- **Body**: Regular, 14-16px, white on dark or dark on light
- **Numbers/Stats**: Bold, larger size, green (`#00ff87`) for highlights
- **Labels**: Uppercase, letter-spacing: 1-2px, 12px

## Logo & Branding

- PL Lion logo: White on purple background
- Usage: Top-left of slides, email header, watermark on diagram

## Team Diagram Styling

Reference: `brainstorming/360_F_429041217_JYmW3luJTIUMpVrLKAOtxz0roYHEhwTq.jpg`

### Pitch
- Background: Rich green (`#1a7f37` or similar grass green)
- Pitch markings: White or light green (`rgba(255,255,255,0.3)`)
- Lines: Center circle, penalty areas, halfway line, goal areas
- Overall dimensions: 1200 × 800px for PNG output

### Player Cards
- **Badge**: Team badge image, 80px × 80px, circular or natural shape
- **Name**: Below badge, white text with dark shadow for readability
  - Font: Bold, 13px
  - Background: Semi-transparent dark pill/capsule (`rgba(0,0,0,0.6)`)
  - Padding: 4px 10px
  - Border-radius: 20px
- **Flag**: To the left of the name, 24px × 18px
- **Connecting lines**: Between players in the same positional line
  - Color: `rgba(255, 255, 255, 0.4)` (semi-transparent white)
  - Stroke width: 2px
  - Style: Straight line connecting player positions in same row

## Google Slides Styling

### Slide Dimensions
Use 16:9 ratio (widescreen): 25.4cm × 14.29cm or 1920×1080 equivalent.

### Slide Types

**Title Slide**:
- Background: `#37003c` (solid purple) or gradient `#37003c → #2D0032`
- Main title: "Premier League" in white, large
- Subtitle: "Team of the Week — Matchweek {N}" in `#00ff87`
- PL logo top-left or center

**Section Divider Slide**:
- Background: `#e90052` (magenta) or `#37003c`
- Section title: Bold, white, centered
- Brief description or icon

**Fixtures & Results Slide**:
- Background: `#37003c`
- Each match row: Home badge | Home name | Score | Away name | Away badge
- Score in `#00ff87` (green)
- Home on left, Away on right
- Alternating row colors: `rgba(255,255,255,0.05)` for every other row

**TOTW Diagram Slide**:
- Background: `#1a7f37` (grass green) — embed the generated PNG
- Title overlay: "Team of the Week — Matchweek {N}" at top

**Formation Report Slide**:
- Background: `#37003c`
- Title in white
- Body text in light grey or white
- Key stats in `#00ff87`

**Player Slide** (1 per player):
- Background: `#37003c`
- Left half: Player image (from API-Football or club site)
- Right half: Player name (bold, white, 32px), team badge, country flag, key stats
- Stats block: Each stat on a row — label (grey) + value (green `#00ff87`)
- Brief explanation text at bottom

**Next Fixtures Slide**:
- Background: `#37003c`
- Title: "Coming Up — Matchweek {N+1}" in `#00ff87`
- List of fixtures: Home team | Date/Time | Away team
- Club badges where possible

### Slide Transitions
Use simple fade or cut transitions. No flashy animations.

## Email Styling

### Layout
```
┌─────────────────────────────────────────┐
│  [PL Logo] Premier League               │  ← Purple header (#37003c)
│  Team of the Week — Matchweek {N}       │
├─────────────────────────────────────────┤
│                                         │
│  🏆 This Week's Team of the Week!       │  ← White/light body
│                                         │
│  [TOTW DIAGRAM IMAGE]                   │
│                                         │
│  [Enthusiastic intro paragraph]         │
│                                         │
│  [Formation] [Key players mention]      │
│                                         │
│  [View Full Report Button] →            │  ← Magenta CTA (#e90052)
│                                         │
├─────────────────────────────────────────┤
│  Sent from 24hrnts@gmail.com            │  ← Purple footer
│  © Premier League TOTW Builder          │
└─────────────────────────────────────────┘
```

### Email Colors
- Header background: `#37003c`
- Header text: `#FFFFFF`
- Body background: `#FFFFFF`
- Body text: `#1a1a2e`
- Accent/CTA: `#e90052`
- Footer background: `#37003c`
- Footer text: `rgba(255,255,255,0.7)`

### Email Tone
- Enthusiastic, upbeat, football fan tone
- Short — no more than 3-4 sentences of body text
- Use football expressions: "What a week!", "Incredible performances", "These players lit up the pitch"
- Avoid corporate/formal language

### Inline Image
The TOTW diagram should be embedded inline in the email (not as an attachment):
- Embed as base64 or using CID (Content-ID) reference
- Max width: 600px (standard email width)
- Alt text: "Premier League Team of the Week - Matchweek {N}"

### PDF Attachment
- Attach the exported presentation PDF
- Filename: `PL-TOTW-Matchweek-{N}.pdf`

## Badge Sizing Reference

| Context | Size |
|---------|------|
| Pitch diagram | 80px × 80px |
| Match results table (slides/email) | 32px × 32px |
| Player slide (next to name) | 48px × 48px |
| Inline in text | 20px × 20px |
| Footer/watermark | 24px × 24px |

## Flag Sizing Reference

| Context | Size |
|---------|------|
| Pitch diagram (next to name) | 24px × 18px |
| Player slide | 32px × 24px |
