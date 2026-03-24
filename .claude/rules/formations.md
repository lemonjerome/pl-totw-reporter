# Football Formations — Domain Knowledge

All analysis, player selection, and diagram rendering must be based on these formation definitions.

## Notation System

Formations are written as defenders-midfielders-forwards (e.g., 4-3-3 = 4 DEF, 3 MID, 3 FWD). When a formation has a distinct defensive midfielder layer, it gets its own number (4-2-3-1 = 4 DEF, 2 CDM, 3 AMF, 1 ST).

## Supported Formations

### 4-3-3
**Line groups**: Defense (GK, RB, CB, CB, LB) | Midfield (CDM, CM, CM) | Attack (RW, ST, LW)
**Positions**: 1 GK, 1 RB, 2 CB, 1 LB, 1 CDM, 2 CM, 1 RW, 1 ST, 1 LW
**Strengths**: Balanced, strong defensive midfield cover, wide attacking options
**Weaknesses**: Wingers must track back; CDM must cover wide areas

**⭐ DEFAULT FORMATION** — use if no clear winner emerges from match data.

Default position mapping for 4-3-3:
- 1 Keeper (GK)
- 1 Right Back (RB)
- 2 Center Backs (CB)
- 1 Left Back (LB)
- 1 Defensive Midfielder (CDM)
- 2 Central Midfielders (CM)
- 1 Right Winger (RW)
- 1 Center Forward / Striker (CF/ST)
- 1 Left Winger (LW)

---

### 4-2-3-1
**Line groups**: Defense (GK, RB, CB, CB, LB) | Def-Mid (CDM, CDM) | Att-Mid (RW, CAM, LW) | Attack (ST)
**Positions**: 1 GK, 1 RB, 2 CB, 1 LB, 2 CDM, 1 CAM, 1 RW, 1 LW, 1 ST
**Strengths**: Double defensive shield, structured, good against counter-attacks
**Weaknesses**: Single striker can be isolated, rigid

---

### 4-4-2
**Line groups**: Defense (GK, RB, CB, CB, LB) | Midfield (RM, CM, CM, LM) | Attack (ST, ST)
**Positions**: 1 GK, 1 RB, 2 CB, 1 LB, 1 RM, 2 CM, 1 LM, 2 ST
**Strengths**: Classic, simple, solid defensive shape, two-striker partnership
**Weaknesses**: Can be overloaded in central midfield against 3-man midfields

---

### 4-4-2 Diamond
**Line groups**: Defense (GK, RB, CB, CB, LB) | Midfield (CDM, CM, CM, CAM) | Attack (ST, ST)
**Positions**: 1 GK, 1 RB, 2 CB, 1 LB, 1 CDM, 2 CM, 1 CAM, 2 ST
**Strengths**: Strong through central areas, creative attacking mid
**Weaknesses**: Vulnerable to wide play

---

### 4-1-4-1
**Line groups**: Defense (GK, RB, CB, CB, LB) | Def-Mid (CDM) | Mid (RM, CM, CM, LM) | Attack (ST)
**Positions**: 1 GK, 1 RB, 2 CB, 1 LB, 1 CDM, 1 RM, 2 CM, 1 LM, 1 ST
**Strengths**: Compact, hard to break down, good counter-attacking base
**Weaknesses**: Lone striker, heavy workload on wide mids

---

### 3-5-2
**Line groups**: Defense (GK, CB, CB, CB) | Midfield (LWB, CM, CM, CM, RWB) | Attack (ST, ST)
**Positions**: 1 GK, 3 CB, 1 LWB, 3 CM, 1 RWB, 2 ST
**Strengths**: Dominates central midfield, strong defensive base, wing-backs provide width
**Weaknesses**: Wing-backs must cover huge ground; vulnerable if outnumbered wide

---

### 3-4-3
**Line groups**: Defense (GK, CB, CB, CB) | Midfield (LWB, CM, CM, RWB) | Attack (LW, ST, RW)
**Positions**: 1 GK, 3 CB, 1 LWB, 2 CM, 1 RWB, 1 LW, 1 ST, 1 RW
**Strengths**: Very attacking, three-pronged attack
**Weaknesses**: Defensively risky, wing-backs key

---

### 5-3-2 / 5-4-1
**Line groups**: Defense (GK, LWB, CB, CB, CB, RWB) | Midfield (CM, CM, CM) | Attack (ST, ST or ST alone)
**Positions (5-3-2)**: 1 GK, 2 WB, 3 CB, 3 CM, 2 ST
**Positions (5-4-1)**: 1 GK, 2 WB, 3 CB, 4 CM (or 2 CM + 2 WM), 1 ST
**Strengths**: Very hard to score against, compact, good transitions
**Weaknesses**: Limited attacking options, relies on lone striker or two strikers

---

### 3-4-2-1 (Christmas Tree-ish 3-back)
**Line groups**: Defense (GK, CB, CB, CB) | Midfield (LWB, CM, CM, RWB) | Attacking Mids (CAM, CAM) | Attack (ST)
**Positions**: 1 GK, 3 CB, 2 WB, 2 CM, 2 CAM, 1 ST
**Strengths**: Creative in final third, solid three-back base
**Weaknesses**: Demands high-quality attacking midfielders

---

## Positional Line Groups (for diagram rendering)

Use these groupings to draw connection lines between players in the same line:

| Line | Positions |
|------|-----------|
| Goalkeeper | GK |
| Defense | CB, RB, LB, LWB, RWB |
| Defensive Midfield | CDM |
| Central Midfield | CM, CAM, RM, LM |
| Attack / Forward | ST, CF, RW, LW |

When rendering the pitch diagram, draw horizontal connector lines between players in the same line group (same horizontal band on the pitch).

---

## Flexible Position Mapping

Players listed in one position may be eligible for adjacent positions:

| Listed As | Can Also Play |
|-----------|---------------|
| LWB | LB, LM |
| RWB | RB, RM |
| CDM | CM |
| CM | CDM, CAM |
| CAM | CM, CF |
| CF | ST, CAM |
| RW | RM, RB (as wing-back) |
| LW | LM, LB (as wing-back) |
| ST | CF |

Apply this mapping when: a formation requires a position that isn't explicitly listed in the player's API data, or when evaluating tiebreakers.

---

## Formation Coordinate Maps (for pitch.html diagram)

Coordinates are expressed as percentages (x=left-to-right, y=top-to-bottom on pitch, GK at bottom).
Positions listed from bottom (GK) to top (attackers).

### 4-3-3
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "RB":  [{"x": 80, "y": 72}],
  "CB":  [{"x": 35, "y": 72}, {"x": 65, "y": 72}],
  "LB":  [{"x": 20, "y": 72}],
  "CDM": [{"x": 50, "y": 55}],
  "CM":  [{"x": 30, "y": 42}, {"x": 70, "y": 42}],
  "RW":  [{"x": 80, "y": 25}],
  "ST":  [{"x": 50, "y": 18}],
  "LW":  [{"x": 20, "y": 25}]
}
```

### 4-2-3-1
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "RB":  [{"x": 80, "y": 75}],
  "CB":  [{"x": 35, "y": 75}, {"x": 65, "y": 75}],
  "LB":  [{"x": 20, "y": 75}],
  "CDM": [{"x": 35, "y": 60}, {"x": 65, "y": 60}],
  "RW":  [{"x": 78, "y": 40}],
  "CAM": [{"x": 50, "y": 38}],
  "LW":  [{"x": 22, "y": 40}],
  "ST":  [{"x": 50, "y": 18}]
}
```

### 4-4-2
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "RB":  [{"x": 80, "y": 72}],
  "CB":  [{"x": 35, "y": 72}, {"x": 65, "y": 72}],
  "LB":  [{"x": 20, "y": 72}],
  "RM":  [{"x": 80, "y": 48}],
  "CM":  [{"x": 35, "y": 48}, {"x": 65, "y": 48}],
  "LM":  [{"x": 20, "y": 48}],
  "ST":  [{"x": 35, "y": 20}, {"x": 65, "y": 20}]
}
```

### 3-5-2
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
  "LWB": [{"x": 10, "y": 55}],
  "CM":  [{"x": 30, "y": 48}, {"x": 50, "y": 48}, {"x": 70, "y": 48}],
  "RWB": [{"x": 90, "y": 55}],
  "ST":  [{"x": 35, "y": 20}, {"x": 65, "y": 20}]
}
```

### 3-4-3
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
  "LWB": [{"x": 12, "y": 52}],
  "CM":  [{"x": 35, "y": 48}, {"x": 65, "y": 48}],
  "RWB": [{"x": 88, "y": 52}],
  "LW":  [{"x": 18, "y": 22}],
  "ST":  [{"x": 50, "y": 15}],
  "RW":  [{"x": 82, "y": 22}]
}
```

### 5-3-2
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "LWB": [{"x": 10, "y": 73}],
  "CB":  [{"x": 28, "y": 78}, {"x": 50, "y": 78}, {"x": 72, "y": 78}],
  "RWB": [{"x": 90, "y": 73}],
  "CM":  [{"x": 25, "y": 50}, {"x": 50, "y": 50}, {"x": 75, "y": 50}],
  "ST":  [{"x": 35, "y": 20}, {"x": 65, "y": 20}]
}
```

### 4-1-4-1
```json
{
  "GK":  [{"x": 50, "y": 90}],
  "RB":  [{"x": 80, "y": 75}],
  "CB":  [{"x": 35, "y": 75}, {"x": 65, "y": 75}],
  "LB":  [{"x": 20, "y": 75}],
  "CDM": [{"x": 50, "y": 60}],
  "RM":  [{"x": 80, "y": 42}],
  "CM":  [{"x": 35, "y": 42}, {"x": 65, "y": 42}],
  "LM":  [{"x": 20, "y": 42}],
  "ST":  [{"x": 50, "y": 18}]
}
```
