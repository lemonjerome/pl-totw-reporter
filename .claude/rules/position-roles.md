# Position Roles & Evaluation Stats — Domain Knowledge

When selecting players for the TOTW, evaluate each player using the stats listed for their position. Primary stats are the main ranking criteria. Secondary stats are used as tiebreakers when two players are equal on primary stats.

## Minimum Requirements

- **Minutes played**: ≥ 60 minutes (players subbed off before 60 min are ineligible)
- **Eligible positions**: Player must have played the position required by the chosen formation (using flexible mapping where applicable — see formations.md)

## Tiebreaker Logic (Algorithmic Shortlist)

1. Compare primary stats. Highest total wins.
2. If tied on primary stats, compare secondary stats.
3. If still tied, prefer the player from a winning team.
4. If still tied, prefer the player with more minutes played.

## Card Penalty (All Positions)

Applied universally as a scoring deduction:
- Yellow card: **-0.3** per card
- Red card: **-1.5** (and disqualifies the player from TOTW consideration)

`statistics[].cards.yellow` / `statistics[].cards.red`

## New Stats Available (SofaScore 2025-26)

These are now extracted and used in scoring. All stored in `PlayerStats`:

| Property | Source field | Notes |
|----------|-------------|-------|
| `xg` | `statistics[].xg` (expectedGoals) | Float, e.g. 1.42 |
| `xa` | `statistics[].xa` (expectedAssists) | Float, e.g. 0.38 |
| `aerial_won_rate` | computed: aerial_won / (aerial_won + aerial_lost) | Float 0–1 |
| `dribble_success_rate` | computed: dribbles.success / dribbles.attempts | Float 0–1 |
| `total_passes` | `statistics[].passes.total` | Integer |
| `accurate_crosses` | `statistics[].passes.accurate_crosses` | Integer |
| `penalty_saves` | `statistics[].penalty.saved` | Integer (GK only) |
| `card_penalty` | computed: -(yellow×0.3) - (red×1.5) | Float, always ≤ 0 |

---

## Goalkeeper (GK)

**Role**: Shot-stopper, command of the box, distribution to defenders and midfielders.

**Primary stats** (rank by total):
1. Saves
2. Clean sheet (0 goals conceded)
3. Penalty saves

**Secondary stats** (tiebreakers in order):
- Goals conceded (lower is better)
- Pass accuracy % (distribution quality)
- Rating

**API field names**:
- `statistics[].goals.saves`
- `statistics[].goals.conceded`
- `statistics[].penalty.saved` — penalty_saves
- `statistics[].games.minutes`
- `statistics[].passes.accuracy`

---

## Center Back (CB)

**Role**: Prevent goals, win aerial duels, organize defense, bring ball out from back.

**Primary stats** (rank by total):
1. Tackles won + interceptions (combined defensive actions)
2. Clearances

**Secondary stats**:
- Blocks + aerial duels won
- `aerial_won_rate` (aerial_won / total aerial duels — quality over raw count)
- Duels won (total ground + aerial)
- Pass accuracy %

**API field names**:
- `statistics[].tackles.total` — tackles_won
- `statistics[].tackles.interceptions`
- `statistics[].tackles.clearances`
- `statistics[].tackles.blocks`
- `statistics[].duels.won`
- `statistics[].duels.aerial_won` + `statistics[].duels.aerial_lost` → `aerial_won_rate`
- `statistics[].passes.accuracy`

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
- `statistics[].tackles.total` — tackles_won
- `statistics[].tackles.interceptions`
- `statistics[].passes.key`
- `statistics[].passes.accurate_crosses` — accurate_crosses
- `statistics[].goals.assists`
- `statistics[].dribbles.success`
- `xa` — expectedAssists

---

## Wing Back (LWB / RWB)

**Role**: Hybrid wide defender/midfielder. Attack and defend the entire flank.

Evaluate like a fullback but weight attacking contribution more heavily.

**Primary stats**:
1. Assists + key passes + xA (attacking)
2. Accurate crosses (wide delivery)

**Secondary stats**:
- Tackles + interceptions (defensive)
- Dribbles completed

**Flexible mapping**: LWB counts for LB or LM slot. RWB counts for RB or RM slot.

**API field names**:
- `statistics[].passes.accurate_crosses`
- `xa` — expectedAssists

---

## Defensive Midfielder (CDM / DMF)

**Role**: Break up attacks, protect the back four, recycle possession efficiently.

**Primary stats**:
1. Tackles won + interceptions (defensive actions)
2. Clearances + duels won

**Secondary stats**:
- Total passes (work rate / involvement — `statistics[].passes.total`)
- Pass accuracy % (recycling quality — elite CDM = 85%+)

**Flexible mapping**: CDM can fill a CM slot if needed.

**API field names**:
- `statistics[].tackles.total`
- `statistics[].tackles.interceptions`
- `statistics[].tackles.clearances`
- `statistics[].duels.won`
- `statistics[].passes.total` — total_passes
- `statistics[].passes.accuracy`

---

## Central Midfielder (CM / CMF)

**Role**: Link defense and attack, cover large areas of the pitch, box-to-box.

**Primary stats**:
1. Key passes + goal contributions
2. xA (chance quality)

**Secondary stats**:
- Total passes (80+ with 85%+ accuracy = game control)
- Pass accuracy %
- Tackles won (defensive contribution)

**Flexible mapping**: CM can fill CDM or CAM slot depending on availability.

**API field names**:
- `statistics[].passes.key`
- `statistics[].goals.total`
- `statistics[].goals.assists`
- `statistics[].passes.total` — total_passes
- `statistics[].passes.accuracy`
- `xa` — expectedAssists

---

## Attacking Midfielder (CAM / AMF)

**Role**: The creative hub behind the striker. Provide the final pass, drive forward with the ball.

**Primary stats**:
1. Key passes + goal contributions
2. xA + xG (creative/goal threat quality)

**Secondary stats**:
- Dribbles completed + dribble_success_rate (unlocking defenses)
- Shots on target

**Flexible mapping**: CAM can fill CM slot. Also consider CF position if no dedicated CAM.

**API field names**:
- `statistics[].passes.key`
- `xa` — expectedAssists
- `xg` — expectedGoals
- `statistics[].dribbles.success` + `statistics[].dribbles.attempts` → `dribble_success_rate`

---

## Right / Left Midfielder (RM / LM)

**Role**: Wide midfielders in a 4-4-2. Defensive and offensive duties across the wide channels.

**Primary stats**:
1. Goals + assists
2. xG + xA (underlying threat even without goals)

**Secondary stats**:
- Dribbles completed + dribble_success_rate
- Key passes
- Accurate crosses

**Flexible mapping**: RM/LM can fill RW/LW if formation has wingers instead.

**API field names**:
- `statistics[].goals.total`
- `statistics[].goals.assists`
- `xg` — expectedGoals
- `xa` — expectedAssists
- `statistics[].dribbles.success`
- `statistics[].passes.accurate_crosses`

---

## Right / Left Winger (RW / LW)

**Role**: Wide attackers. Create chances, take on defenders 1v1, score and assist.

**Primary stats**:
1. Goals + assists
2. xG + xA (underlying quality — a winger with xG=1.5 and 0 goals may outrank a 1-goal tap-in scorer)

**Secondary stats**:
- Dribbles completed + dribble_success_rate (beating men)
- Key passes
- Accurate crosses

**API field names**:
- `statistics[].goals.total`
- `statistics[].goals.assists`
- `xg` — expectedGoals
- `xa` — expectedAssists
- `statistics[].dribbles.success` + `statistics[].dribbles.attempts` → `dribble_success_rate`
- `statistics[].shots.on`
- `statistics[].passes.accurate_crosses`

---

## Striker / Center Forward (ST / CF)

**Role**: Primary goalscorer. Lead the line, hold up play, finish chances.

**Primary stats**:
1. Goals
2. Shots on target
3. xG (expected goals — shows if striker was in the right positions)

**Secondary stats**:
- Shot conversion rate (goals / total shots)
- Assists
- Aerial duels won + aerial_won_rate (hold-up play, heading threat)
- Dribbles completed

**Flexible mapping**: ST and CF are interchangeable. A CF playing in advanced positions is counted as ST.

**API field names**:
- `statistics[].goals.total`
- `statistics[].shots.on`
- `statistics[].shots.total`
- `statistics[].goals.assists`
- `xg` — expectedGoals
- `statistics[].duels.aerial_won` + `statistics[].duels.aerial_lost` → `aerial_won_rate`

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
