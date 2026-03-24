# Position Roles & Evaluation Stats — Domain Knowledge

When selecting players for the TOTW, evaluate each player using the stats listed for their position. Primary stats are the main ranking criteria. Secondary stats are used as tiebreakers when two players are equal on primary stats.

## Minimum Requirements

- **Minutes played**: ≥ 60 minutes (players subbed off before 60 min are ineligible)
- **Eligible positions**: Player must have played the position required by the chosen formation (using flexible mapping where applicable — see formations.md)

## Tiebreaker Logic

1. Compare primary stats. Highest total wins.
2. If tied on primary stats, compare secondary stats.
3. If still tied, prefer the player from a winning team.
4. If still tied, prefer the player with more minutes played.

---

## Goalkeeper (GK)

**Role**: Shot-stopper, command of the box, distribution to defenders and midfielders.

**Primary stats** (rank by total):
1. Saves
2. Clean sheet (1 point = 0 goals conceded + team won or drew)

**Secondary stats** (tiebreakers in order):
- Save percentage (saves / total shots on target faced)
- Goals conceded (lower is better)
- Penalty saves
- Distribution accuracy (passes completed %)

**API field names** (`fixtures/players` response):
- `statistics[].goals.saves`
- `statistics[].goals.conceded`
- `statistics[].games.minutes`
- `statistics[].passes.accuracy`

---

## Center Back (CB)

**Role**: Prevent goals, win aerial duels, organize defense, bring ball out from back.

**Primary stats** (rank by total):
1. Tackles won
2. Interceptions
3. Clearances

**Secondary stats**:
- Aerial duels won
- Blocks
- Pass accuracy %
- Clean sheet contribution (team clean sheet while player was on pitch)

**API field names**:
- `statistics[].tackles.total`
- `statistics[].tackles.interceptions`
- `statistics[].tackles.blocks`
- `statistics[].duels.won`

---

## Right Back / Left Back (RB / LB)

**Role**: Defend wide areas, support attacks with overlapping runs, deliver crosses.

**Primary stats**:
1. Tackles won + interceptions (combined defensive actions)
2. Key passes + assists (attacking contribution)

**Secondary stats**:
- Crosses (total)
- Dribbles completed
- Duels won
- Minutes played

**API field names**:
- `statistics[].tackles.total`
- `statistics[].tackles.interceptions`
- `statistics[].passes.key`
- `statistics[].goals.assists`
- `statistics[].dribbles.success`

---

## Wing Back (LWB / RWB)

**Role**: Hybrid wide defender/midfielder. Attack and defend the entire flank.

Evaluate like a fullback but weight attacking contribution more heavily.

**Primary stats**:
1. Key passes + assists (attacking)
2. Tackles + interceptions (defensive)

**Secondary stats**:
- Crosses
- Dribbles completed
- Distance covered (if available)

**Flexible mapping**: LWB counts for LB or LM slot. RWB counts for RB or RM slot.

---

## Defensive Midfielder (CDM / DMF)

**Role**: Break up attacks, protect the back four, recycle possession efficiently.

**Primary stats**:
1. Tackles won
2. Interceptions

**Secondary stats**:
- Pass accuracy %
- Duels won
- Balls recovered (if available)
- Key passes

**Flexible mapping**: CDM can fill a CM slot if needed.

**API field names**:
- `statistics[].tackles.total`
- `statistics[].tackles.interceptions`
- `statistics[].passes.accuracy`
- `statistics[].duels.won`

---

## Central Midfielder (CM / CMF)

**Role**: Link defense and attack, cover large areas of the pitch, box-to-box.

**Primary stats**:
1. Key passes (chances created)
2. Goals + assists

**Secondary stats**:
- Pass accuracy %
- Tackles won
- Dribbles completed
- Total passes

**Flexible mapping**: CM can fill CDM or CAM slot depending on availability.

**API field names**:
- `statistics[].passes.key`
- `statistics[].goals.total`
- `statistics[].goals.assists`
- `statistics[].passes.accuracy`

---

## Attacking Midfielder (CAM / AMF)

**Role**: The creative hub behind the striker. Provide the final pass, drive forward with the ball.

**Primary stats**:
1. Key passes (chances created)
2. Goals + assists

**Secondary stats**:
- Dribbles completed
- Shots on target
- Pass accuracy %

**Flexible mapping**: CAM can fill CM slot. Also consider CF position if no dedicated CAM.

---

## Right / Left Midfielder (RM / LM)

**Role**: Wide midfielders in a 4-4-2. Defensive and offensive duties across the wide channels.

**Primary stats**:
1. Goals + assists
2. Key passes

**Secondary stats**:
- Dribbles completed
- Crosses
- Tackles won

**Flexible mapping**: RM/LM can fill RW/LW if formation has wingers instead.

---

## Right / Left Winger (RW / LW)

**Role**: Wide attackers. Create chances, take on defenders 1v1, score and assist.

**Primary stats**:
1. Goals + assists
2. Dribbles completed

**Secondary stats**:
- Key passes
- Shots on target
- Crosses

**API field names**:
- `statistics[].goals.total`
- `statistics[].goals.assists`
- `statistics[].dribbles.success`
- `statistics[].shots.on`
- `statistics[].passes.key`

---

## Striker / Center Forward (ST / CF)

**Role**: Primary goalscorer. Lead the line, hold up play, finish chances.

**Primary stats**:
1. Goals
2. Shots on target

**Secondary stats**:
- Assists
- Shot conversion rate (goals / total shots)
- Aerial duels won
- Dribbles completed

**Flexible mapping**: ST and CF are interchangeable. A CF playing in advanced positions is counted as ST.

**API field names**:
- `statistics[].goals.total`
- `statistics[].shots.on`
- `statistics[].shots.total`
- `statistics[].goals.assists`

---

## Position Abbreviation Reference

| Abbreviation | Full Name | Line |
|---|---|---|
| GK | Goalkeeper | Goalkeeper |
| RB | Right Back | Defense |
| CB | Center Back | Defense |
| LB | Left Back | Defense |
| RWB | Right Wing Back | Defense/Midfield |
| LWB | Left Wing Back | Defense/Midfield |
| CDM | Central Defensive Midfielder | Defensive Midfield |
| CM | Central Midfielder | Midfield |
| CAM | Central Attacking Midfielder | Midfield |
| RM | Right Midfielder | Midfield |
| LM | Left Midfielder | Midfield |
| RW | Right Winger | Attack |
| LW | Left Winger | Attack |
| CF | Center Forward | Attack |
| ST | Striker | Attack |

---

## API-Football Position Codes

API-Football uses these position strings in lineup data:
- `"G"` = Goalkeeper
- `"D"` = Defender (CB, RB, LB, WB)
- `"M"` = Midfielder (CDM, CM, CAM, RM, LM)
- `"F"` = Forward (RW, LW, ST, CF)

Use the `grid` field in lineup data to determine the player's exact position on the pitch (e.g., `"1:1"` = row 1 from defense, position 1 from left).
