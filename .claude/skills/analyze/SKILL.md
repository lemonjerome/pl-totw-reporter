---
name: analyze
description: Analyze Premier League matchweek data to select the best formation and TOTW players. Run after /research. Outputs formation report and player selections. Usage: /analyze [matchweek_number]
---

# Analyze — Formation & Player Selection (Enhanced)

Select the TOTW formation and 11 players for matchweek $ARGUMENTS.

## Prerequisites

Verify research data exists:
```bash
ls data/2025-26/matchweek-$ARGUMENTS/fixtures.json
```

If missing, run `/research $ARGUMENTS` first.

---

## Step 1: Formation Analysis

```bash
python scripts/formation_analyzer.py $ARGUMENTS
```

Report the result:
```
Formation selected: {formation}
Used by winning teams: {N} times
Teams: {team list}
```

---

## Step 2: Enhanced Shortlist Generation

```bash
python scripts/player_evaluator.py $ARGUMENTS
```

This outputs `output/matchweek-$ARGUMENTS/analysis/shortlists.json` — top 3 candidates per position slot, ranked by enhanced stat scoring (xG, xA, aerial_won_rate, dribble_success_rate, accurate_crosses, total_passes, card penalties, and more).

Read `shortlists.json` and extract all slot entries. Note the formation and position at each slot index.

---

## Step 3: Split Positions into 3 Groups

Using floor division on the 11 slots:
- **Analyst 1**: slots 0–3 (4 slots)
- **Analyst 2**: slots 4–7 (4 slots)
- **Analyst 3**: slots 8–10 (3 slots)

---

## Step 4: Launch 3 Analyst Subagents in Parallel

**CRITICAL**: Spawn all 3 researcher agents in a **single message** so they run in parallel. Do NOT send them sequentially.

Each analyst receives a prompt with their specific slot assignments and the full position knowledge below. Replace `{N}`, `{formation}`, and slot details from the actual shortlists.json you read.

---

### Analyst Prompt Template

```
You are an EPL football analyst selecting the Premier League Team of the Week.

Matchweek: {N} | Formation: {formation}
Your assigned positions (by slot index): {slot_idx}: {position}, {slot_idx}: {position}, ...

== YOUR TASK ==

For each of your assigned slots:
1. Read `output/matchweek-{N}/analysis/shortlists.json` (your slots section)
2. Review all 3 candidates — their stats snapshot is already in the shortlist
3. If you need deeper context, read `data/2025-26/matchweek-{N}/players_{fixture_id}.json`
4. Apply expert analysis (rules below) to pick the SINGLE best player for that slot
5. Write your decisions to `output/matchweek-{N}/analysis/analyst_{1|2|3}.json`

== POSITION EVALUATION RULES ==

**GK**: Saves count is primary. A GK with 7 saves in a 1-0 win > one with 3 saves in a 4-0 win.
Check penalty_saves — rare but decisive. Clean sheet confirms defensive quality.
A GK who conceded 2 but made 9 saves can still win over one who kept a cheap clean sheet.

**CB**: Tackles won + interceptions are primary — this shows the CB was genuinely tested.
Secondary: clearances (volume of defensive work), aerial_won_rate (dominance in the air, not just raw count).
Pass accuracy shows ball-playing quality. Prefer a CB with 8 tackles over one with 2 tackles and a clean sheet they barely contributed to.

**RB / LB**: Dual role — reward BOTH defensive solidity AND attacking output.
Key stats: defensive_actions AND (assists + key_passes + accurate_crosses + xa).
A fullback with 0 tackles but 2 assists is usually more TOTW-worthy than one with 4 tackles and 0 attacking output.
Accurate crosses show consistent wide delivery quality.

**CDM**: Tackles + interceptions dominate. These are the battles that define a holding midfielder.
Also check total_passes — a CDM with 90 passes at 88% accuracy was the team's engine.
Pass accuracy below 70% is a red flag even with high tackle numbers.

**CM**: Key passes and goal contributions are primary. xA adds nuance (chance quality, not just volume).
Total passes (80+) with high accuracy (85%+) shows the CM controlled the game.
Also check tackles_won — a box-to-box CM who won defensive duels scores extra.

**CAM**: Creative output is everything. key_passes + xA + goal contributions.
Check dribble_success_rate — a CAM who completed 4/5 dribbles unlocked defenses repeatedly.
Shots on target shows their personal goal threat.

**RW / LW / RM / LM**: Goals + assists are primary. BUT: a player with 0G/0A but xG=1.5 and
6 dribbles completed may have been the best winger — they were just unlucky or the finishing
wasn't theirs. xG+xA together tell the real story.
Check dribble_success_rate: 4/4 dribbles > 8/15 dribbles even if raw count is higher.
Accurate_crosses matter for wide players in wide systems.

**ST / CF**: Goals are king. But context matters — a ST with 0 goals, xG=1.8, 7 shots on target
was central to the attack and got unlucky. Compare their xG vs. a ST who scored 1 tap-in.
aerial_won shows physical dominance in the box. Shot conversion separates clinical finishers.

== QUALITATIVE FACTORS ==
- **Opponent quality**: 5 tackles vs Man City/Arsenal/Liverpool > 5 tackles vs a relegated side
- **Game context**: A last-minute save or tackle that preserves a win outweighs equivalent stats in a 4-0 game
- **Team context**: 2 assists in a 2-1 win > 2 assists in a 5-0 win (your contribution was decisive)
- **DO NOT auto-pick rank 1** — that is an algorithmic guess, you are here to apply judgment algorithms cannot
- **Red card = automatic disqualification** regardless of stats before the card
- When in doubt between two similar candidates, pick the one from the winning team

== OUTPUT FORMAT ==

Write a JSON file using the Write tool to:
`output/matchweek-{N}/analysis/analyst_{1|2|3}.json`

Schema (exact — the merge script depends on these field names):
```json
{
  "analyst_id": 1,
  "matchweek": {N},
  "selections": [
    {
      "slot_index": 0,
      "position": "GK",
      "player_name": "Player Name",
      "player_id": 12345,
      "fixture_id": 678,
      "key_stat": "7 saves, clean sheet, rating 7.9",
      "selection_reason": "Made 7 saves including two crucial stops in the second half to preserve a 1-0 win over Spurs. Highest save count of any GK this matchweek against a genuine top-6 attack.",
      "rejected": [
        "David Raya — only 3 saves in a comfortable 3-0 win, not tested",
        "Nick Pope — conceded 2, limited to 4 saves in a loss"
      ]
    }
  ]
}
```

Write all your slot selections in one JSON file. Use `slot_index` exactly as given.
```

---

## Step 5: Wait for All 3 Analysts to Complete

All 3 analyst agents must finish before proceeding.

---

## Step 6: Merge Analyst Selections

```bash
python scripts/merge_analyst_selections.py $ARGUMENTS
```

This reads `analyst_1.json`, `analyst_2.json`, `analyst_3.json`, looks up each player from the raw cache by `player_id`, and writes the final `players.json`. Any slot not covered by an analyst falls back to shortlist rank 1.

---

## Step 7: Report Generation

```bash
python scripts/report_generator.py $ARGUMENTS
```

---

## Output Summary

```
Analysis complete for Matchweek {N}:
Formation: {N-N-N}
Players selected:
  GK:  {name} ({club}) — {key_stat}
  RB:  {name} ({club}) — {key_stat}
  CB:  {name} ({club}) — {key_stat}
  CB:  {name} ({club}) — {key_stat}
  LB:  {name} ({club}) — {key_stat}
  CDM: {name} ({club}) — {key_stat}
  ...

Reports saved to: output/matchweek-{N}/analysis/
```
