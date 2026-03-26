# TOTW Selection Criteria — Domain Knowledge

Rules for selecting the Premier League Team of the Week formation and players.

## Step 1: Determine the Formation

1. Load lineup data for all completed fixtures in the matchweek.
2. Count how many times each formation was used by **winning teams only**.
3. The formation with the highest count among winners is selected.
4. **Tie**: If two formations are tied on wins, pick the one with more total goals scored by teams using it.
5. **No clear winner** (all teams lost or drew, or no formation used more than once): Default to **4-3-3**.
6. **Default 4-3-3** spec:
   - 1 GK, 1 RB, 2 CB, 1 LB, 1 CDM, 2 CM, 1 RW, 1 CF/ST, 1 LW

Also prepare a short formation explanation:
- Which teams used it and what were their results?
- Why does this formation make sense for the week's performances?
- If default: explain why no formation stood out.

---

## Step 2: Select Players Per Position

For each position slot in the chosen formation:

### 2.1 Build the Candidate Pool

Collect all players from the matchweek who:
- Played the required position (using flexible position mapping from formations.md)
- Played ≥ 60 minutes
- Have valid stats from the `fixtures/players` API response

### 2.2 Rank Candidates

Use position-specific primary stats (see position-roles.md) to rank candidates.

Apply tiebreaker logic in this order:
1. Primary stats (e.g., goals for strikers, saves for GK)
2. Secondary stats (e.g., assists, key passes)
3. Player from a winning team (prefer winner over draw/loss)
4. Most minutes played

### 2.3 No Team Limit

**There is no limit on players from the same team.** If one team dominated the matchweek statistically, multiple players from that team can be selected. Select purely on merit.

### 2.4 Handle Position Flexibility

If the chosen formation requires a position that has very few or no eligible players:
- Apply flexible position mapping (e.g., if no CDM is available, use a CM)
- Note the adaptation in the formation report

---

## Step 3: Validate the Selection

Before finalizing, check:
- Every position in the formation has exactly 1 player selected.
- All 11 players played ≥ 60 minutes.
- No position slot is empty.
- Player names and team names are correctly linked.

If a slot cannot be filled (e.g., no goalkeeper played 60+ min), select the GK with the most minutes regardless of the 60-minute rule and note it in the report.

---

## Step 4: Create Player Reports

For each selected player, write a synthesis report including:

1. **Stats summary**: List all primary and relevant secondary stats from the matchweek.
2. **Match context**: Which game did they play? Score and result.
3. **Key moments**: Specific goals, assists, saves, crucial defensive actions derived from stats.
4. **Why selected**: Brief explanation of why this player stood above the rest at their position.
5. **Notable numbers**: Bold or highlight the key stat (e.g., "2 goals and 1 assist in a 4-0 victory").

Source for reports: SofaScore player stats (via soccerdata_client.py).

---

## Step 5: Handle Matchweek Status

### Complete Matchweek
All fixtures have status `FT`, `AET`, or `PEN`. Proceed with full TOTW generation.

### Incomplete Matchweek
Some fixtures still have status `NS`, `1H`, `HT`, `2H`, `ET`:
- List all completed match results (with scores)
- List all pending matches with scheduled date/time (convert to local time if possible)
- Inform the user: "Matchweek {N} is not yet complete. {X} of 10 matches have finished."
- Ask: "Would you like the TOTW for the previous matchweek ({N-1}) instead?"
- Do NOT generate TOTW with incomplete data.

### Future Matchweek
All fixtures have status `NS` and the date is in the future:
- List all scheduled fixtures with dates/times
- Inform the user: "Matchweek {N} hasn't started yet. It begins on {date}."
- Ask: "Would you like the TOTW for the most recently completed matchweek instead?"

### No Matchweek Specified
Use the `/fixtures/rounds?current=true` endpoint to find the current round.
Then fetch those fixtures and check their statuses.
If the current round is complete → build TOTW for it.
If not → follow the incomplete matchweek logic above.

---

## Example TOTW Output Format

```
## Premier League Team of the Week — Matchweek 30

**Formation**: 4-3-3
**Formation rationale**: Most used by winning teams (3 teams won using 4-3-3).

### XI
| Position | Player | Team | Rating |
|----------|--------|------|--------|
| GK | Jordan Pickford | Everton | 8.2 |
| RB | Trent Alexander-Arnold | Liverpool | 8.5 |
| CB | Virgil van Dijk | Liverpool | 8.0 |
| CB | William Saliba | Arsenal | 7.8 |
| LB | Andrew Robertson | Liverpool | 8.1 |
| CDM | Rodri | Man City | 8.3 |
| CM | Martin Ødegaard | Arsenal | 8.6 |
| CM | Bruno Fernandes | Man United | 7.9 |
| RW | Mohamed Salah | Liverpool | 9.1 |
| ST | Erling Haaland | Man City | 9.4 |
| LW | Bukayo Saka | Arsenal | 8.7 |
```
