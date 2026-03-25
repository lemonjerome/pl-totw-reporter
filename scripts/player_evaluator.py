"""
Player Evaluator for the EPL TOTW Builder.

Loads cached player stats for a matchweek, applies position-specific ranking
criteria (from position-roles.md), and selects the best player for each
position slot in the chosen formation.

CLI:
    python scripts/player_evaluator.py 30
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_models import (
    Player,
    PlayerCards,
    PlayerDribbles,
    PlayerDuels,
    PlayerGames,
    PlayerGoals,
    PlayerPasses,
    PlayerPenalty,
    PlayerShots,
    PlayerStats,
    PlayerTackles,
    SelectedFormation,
    TOTWPlayer,
    TOTWSelection,
)
from scripts.utils import (
    get_country_code,
    load_json_cache,
    matchweek_analysis_dir,
    matchweek_data_dir,
    save_json_cache,
)

# ---------------------------------------------------------------------------
# Position score functions — higher score = better candidate
# Each function returns a tuple for sorting (descending)
# ---------------------------------------------------------------------------

def score_gk(p: Player) -> tuple:
    """GK: saves first, then clean sheet bonus, then goals conceded (inverted)."""
    saves = p.stats.saves
    clean = 1 if p.stats.clean_sheet else 0
    conceded = -(p.stats.goals.conceded or 0)
    rating = p.stats.rating_float
    return (saves, clean, conceded, rating)


def score_cb(p: Player) -> tuple:
    """CB: tackles + interceptions + blocks, then rating."""
    tackles = p.stats.tackles_won
    intercepts = p.stats.interceptions
    blocks = p.stats.tackles.blocks or 0
    duels = p.stats.duels_won
    rating = p.stats.rating_float
    return (tackles + intercepts, blocks, duels, rating)


def score_fb(p: Player) -> tuple:
    """RB/LB: defensive actions + attacking contribution."""
    defensive = p.stats.defensive_actions
    attacking = p.stats.key_passes + (p.stats.assists * 2)  # assists weighted
    dribbles = p.stats.dribbles_completed
    rating = p.stats.rating_float
    return (defensive, attacking, dribbles, rating)


def score_wb(p: Player) -> tuple:
    """LWB/RWB: attacking weighted more than fullback."""
    attacking = (p.stats.assists * 3) + (p.stats.key_passes * 2) + p.stats.dribbles_completed
    defensive = p.stats.defensive_actions
    rating = p.stats.rating_float
    return (attacking, defensive, rating)


def score_cdm(p: Player) -> tuple:
    """CDM: tackles + interceptions primary."""
    tackles = p.stats.tackles_won
    intercepts = p.stats.interceptions
    duels = p.stats.duels_won
    pass_acc = p.stats.pass_accuracy
    rating = p.stats.rating_float
    return (tackles + intercepts, duels, pass_acc, rating)


def score_cm(p: Player) -> tuple:
    """CM: key passes + goal contributions."""
    key_passes = p.stats.key_passes
    goal_contrib = p.stats.goal_contributions
    pass_acc = p.stats.pass_accuracy
    rating = p.stats.rating_float
    return (key_passes, goal_contrib, pass_acc, rating)


def score_cam(p: Player) -> tuple:
    """CAM: chances created + goal contributions + dribbles."""
    key_passes = p.stats.key_passes
    goal_contrib = p.stats.goal_contributions
    dribbles = p.stats.dribbles_completed
    shots_ot = p.stats.shots_on_target
    rating = p.stats.rating_float
    return (key_passes, goal_contrib, dribbles, shots_ot, rating)


def score_winger(p: Player) -> tuple:
    """RW/LW/RM/LM: goals + assists + dribbles."""
    goals = p.stats.goals_scored
    assists = p.stats.assists
    dribbles = p.stats.dribbles_completed
    key_passes = p.stats.key_passes
    shots_ot = p.stats.shots_on_target
    rating = p.stats.rating_float
    return (goals + assists, dribbles, key_passes, shots_ot, rating)


def score_st(p: Player) -> tuple:
    """ST/CF: goals primary, then shots on target, then conversion."""
    goals = p.stats.goals_scored
    shots_ot = p.stats.shots_on_target
    conversion = p.stats.shot_conversion
    assists = p.stats.assists
    rating = p.stats.rating_float
    return (goals, shots_ot, conversion, assists, rating)


# ---------------------------------------------------------------------------
# Position slot → score function + eligible API position codes
# ---------------------------------------------------------------------------

# Maps formation position slot → (score_fn, eligible_api_positions, eligible_slots)
# eligible_api_positions: what API `position` codes qualify (G/D/M/F)
# We also check flexible position mapping by trying adjacent slots
POSITION_CONFIG: dict[str, dict] = {
    "GK":  {"score_fn": score_gk,     "api_pos": {"G"}},
    "RB":  {"score_fn": score_fb,     "api_pos": {"D"}},
    "CB":  {"score_fn": score_cb,     "api_pos": {"D"}},
    "LB":  {"score_fn": score_fb,     "api_pos": {"D"}},
    "RWB": {"score_fn": score_wb,     "api_pos": {"D", "M"}},
    "LWB": {"score_fn": score_wb,     "api_pos": {"D", "M"}},
    "CDM": {"score_fn": score_cdm,    "api_pos": {"M"}},
    "CM":  {"score_fn": score_cm,     "api_pos": {"M"}},
    "CAM": {"score_fn": score_cam,    "api_pos": {"M"}},
    "RM":  {"score_fn": score_winger, "api_pos": {"M"}},
    "LM":  {"score_fn": score_winger, "api_pos": {"M"}},
    "RW":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "LW":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "ST":  {"score_fn": score_st,     "api_pos": {"F", "M"}},
    "CF":  {"score_fn": score_st,     "api_pos": {"F", "M"}},
}

# Flexible fallback — if not enough candidates for a slot, also consider these api_pos
FLEXIBLE_API_POS: dict[str, set[str]] = {
    "CDM": {"D"},   # Some DMs listed as defenders
    "CM":  {"D"},
    "CAM": {"F"},
    "ST":  {"M"},
    "RW":  {"M"},
    "LW":  {"M"},
}


def _parse_player_from_cache(
    player_raw: dict,
    team_raw: dict,
    fixture_id: int,
    fixture_winner: Optional[str],
    team_side: str,  # "home" or "away"
) -> Optional[Player]:
    """Parse a player dict from the players cache into a Player model."""
    p = player_raw.get("player", {})
    stats_list = player_raw.get("statistics", [{}])
    stats_raw = stats_list[0] if stats_list else {}

    player_id = p.get("id")
    name = p.get("name", "Unknown")
    photo = p.get("photo", "")

    games_raw = stats_raw.get("games", {})
    minutes = games_raw.get("minutes") or 0
    position = games_raw.get("position") or ""
    rating = games_raw.get("rating") or None
    captain = games_raw.get("captain", False)

    goals_raw = stats_raw.get("goals", {})
    shots_raw = stats_raw.get("shots", {})
    passes_raw = stats_raw.get("passes", {})
    tackles_raw = stats_raw.get("tackles", {})
    duels_raw = stats_raw.get("duels", {})
    dribbles_raw = stats_raw.get("dribbles", {})
    cards_raw = stats_raw.get("cards", {})
    penalty_raw = stats_raw.get("penalty", {})

    stats = PlayerStats(
        games=PlayerGames(
            minutes=minutes,
            position=position or None,
            rating=str(rating) if rating else None,
            captain=captain,
        ),
        goals=PlayerGoals(
            total=goals_raw.get("total"),
            conceded=goals_raw.get("conceded"),
            assists=goals_raw.get("assists"),
            saves=goals_raw.get("saves"),
        ),
        shots=PlayerShots(
            total=shots_raw.get("total"),
            on=shots_raw.get("on"),
        ),
        passes=PlayerPasses(
            total=passes_raw.get("total"),
            key=passes_raw.get("key"),
            accuracy=str(passes_raw["accuracy"]) if passes_raw.get("accuracy") is not None else None,
        ),
        tackles=PlayerTackles(
            total=tackles_raw.get("total"),
            blocks=tackles_raw.get("blocks"),
            interceptions=tackles_raw.get("interceptions"),
        ),
        duels=PlayerDuels(
            total=duels_raw.get("total"),
            won=duels_raw.get("won"),
        ),
        dribbles=PlayerDribbles(
            attempts=dribbles_raw.get("attempts"),
            success=dribbles_raw.get("success"),
        ),
        cards=PlayerCards(
            yellow=cards_raw.get("yellow", 0),
            red=cards_raw.get("red", 0),
        ),
        penalty=PlayerPenalty(
            won=penalty_raw.get("won"),
            committed=penalty_raw.get("commited") or penalty_raw.get("committed"),
            scored=penalty_raw.get("scored"),
            missed=penalty_raw.get("missed"),
            saved=penalty_raw.get("saved"),
        ),
    )

    # Determine fixture result from team perspective
    if fixture_winner is None:
        fixture_result = "draw"
    elif fixture_winner == team_side:
        fixture_result = "win"
    else:
        fixture_result = "loss"

    return Player(
        player_id=player_id,
        name=name,
        photo=photo,
        team_id=team_raw["id"],
        team_name=team_raw["name"],
        team_logo=team_raw["logo"],
        nationality="",  # not available in players endpoint
        country_code="xx",
        position_code=position,
        stats=stats,
        fixture_id=fixture_id,
        fixture_result=fixture_result,
    )


def load_all_players(matchweek: int) -> list[Player]:
    """Load all players from cached player stats for the matchweek."""
    fixtures_path = matchweek_data_dir(matchweek) / "fixtures.json"
    fixtures = load_json_cache(fixtures_path) or []

    all_players: list[Player] = []

    for fixture in fixtures:
        status = fixture["fixture"]["status"]["short"]
        if status not in ("FT", "AET", "PEN"):
            continue

        fixture_id = fixture["fixture"]["id"]
        home_team = fixture["teams"]["home"]
        away_team = fixture["teams"]["away"]

        home_winner = home_team.get("winner")
        away_winner = away_team.get("winner")
        if home_winner:
            fixture_winner = "home"
        elif away_winner:
            fixture_winner = "away"
        else:
            fixture_winner = None

        players_path = matchweek_data_dir(matchweek) / f"players_{fixture_id}.json"
        players_data = load_json_cache(players_path) or []

        for team_data in players_data:
            team_raw = team_data["team"]
            # Determine side (home or away)
            side = "home" if team_raw["id"] == home_team["id"] else "away"

            for player_raw in team_data.get("players", []):
                p = _parse_player_from_cache(
                    player_raw, team_raw, fixture_id, fixture_winner, side
                )
                if p:
                    all_players.append(p)

    return all_players


def select_players_for_formation(
    formation: SelectedFormation,
    all_players: list[Player],
) -> list[TOTWPlayer]:
    """
    Select the best player for each position slot in the formation.
    Returns list of TOTWPlayer (11 total).
    """
    positions = formation.positions  # e.g. ["GK", "RB", "CB", "CB", ...]
    selected: list[TOTWPlayer] = []
    used_player_ids: set[int] = set()

    # Count how many of each slot we need
    slot_counts: dict[str, int] = {}
    for pos in positions:
        slot_counts[pos] = slot_counts.get(pos, 0) + 1

    # Process each unique slot type, handling duplicates (e.g. 2x CB)
    processed_slots: dict[str, int] = {}  # tracks how many of each slot filled

    for position_slot in positions:
        # Get config for this position
        config = POSITION_CONFIG.get(position_slot)
        if not config:
            # Unknown position — skip
            continue

        score_fn = config["score_fn"]
        api_pos = config["api_pos"]
        flex_api_pos = FLEXIBLE_API_POS.get(position_slot, set())

        # Find eligible candidates not already selected
        candidates = [
            p for p in all_players
            if p.player_id not in used_player_ids
            and p.is_eligible
            and p.position_code in api_pos
        ]

        # Fallback: include flexible positions if needed
        if not candidates:
            candidates = [
                p for p in all_players
                if p.player_id not in used_player_ids
                and p.is_eligible
                and p.position_code in (api_pos | flex_api_pos)
            ]

        # Tiebreaker: prefer player from winning team (encoded in fixture_result)
        def sort_key(p: Player):
            score = score_fn(p)
            win_bonus = 1 if p.fixture_result == "win" else 0
            minutes = p.stats.minutes_played
            return score + (win_bonus,) + (minutes,)

        candidates.sort(key=sort_key, reverse=True)

        if not candidates:
            # No candidates at all — fill with whoever has most minutes at that api_pos
            fallback = [
                p for p in all_players
                if p.player_id not in used_player_ids
                and p.position_code in (api_pos | flex_api_pos | {"G", "D", "M", "F"})
            ]
            fallback.sort(key=lambda p: p.stats.minutes_played, reverse=True)
            candidates = fallback[:1]

        if not candidates:
            continue

        best = candidates[0]
        used_player_ids.add(best.player_id)

        key_stat = _build_key_stat(best, position_slot)
        reason = _build_reason(best, position_slot)

        selected.append(TOTWPlayer(
            position_slot=position_slot,
            player=best,
            selection_reason=reason,
            key_stat=key_stat,
        ))

    return selected


def _build_key_stat(player: Player, slot: str) -> str:
    """Build a concise key stat string for a player at a position."""
    s = player.stats
    parts = []

    if slot == "GK":
        if s.saves > 0:
            parts.append(f"{s.saves} save{'s' if s.saves != 1 else ''}")
        if s.clean_sheet:
            parts.append("clean sheet")
        if s.goals.conceded is not None:
            parts.append(f"{s.goals.conceded} conceded")

    elif slot in ("CB", "RB", "LB", "RWB", "LWB"):
        if s.tackles_won > 0:
            parts.append(f"{s.tackles_won} tackle{'s' if s.tackles_won != 1 else ''}")
        if s.interceptions > 0:
            parts.append(f"{s.interceptions} interception{'s' if s.interceptions != 1 else ''}")
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")

    elif slot in ("CDM", "CM"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")
        if s.key_passes > 0:
            parts.append(f"{s.key_passes} key pass{'es' if s.key_passes != 1 else ''}")
        if s.tackles_won > 0:
            parts.append(f"{s.tackles_won} tackle{'s' if s.tackles_won != 1 else ''}")

    elif slot in ("CAM", "RW", "LW", "RM", "LM"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")
        if s.key_passes > 0:
            parts.append(f"{s.key_passes} key pass{'es' if s.key_passes != 1 else ''}")
        if s.dribbles_completed > 0:
            parts.append(f"{s.dribbles_completed} dribble{'s' if s.dribbles_completed != 1 else ''}")

    elif slot in ("ST", "CF"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")
        if s.shots_on_target > 0:
            parts.append(f"{s.shots_on_target} shot{'s' if s.shots_on_target != 1 else ''} on target")

    if s.rating_float > 0:
        parts.append(f"rating {s.games.rating}")

    return ", ".join(parts) if parts else f"rating {s.games.rating or 'N/A'}"


def _build_reason(player: Player, slot: str) -> str:
    """Build a brief selection reason."""
    s = player.stats
    result = player.fixture_result or ""
    result_str = {"win": "winning", "draw": "draw", "loss": "losing"}.get(result, "")

    lines = []

    if slot == "GK":
        if s.saves > 0:
            lines.append(f"Made {s.saves} save(s).")
        if s.clean_sheet:
            lines.append("Kept a clean sheet.")
    elif slot in ("CB", "RB", "LB", "RWB", "LWB"):
        if s.defensive_actions > 0:
            lines.append(f"{s.defensive_actions} combined tackles + interceptions.")
    elif slot in ("CDM", "CM"):
        if s.key_passes > 0:
            lines.append(f"{s.key_passes} key passes created.")
        if s.goal_contributions > 0:
            lines.append(f"{s.goal_contributions} goal contribution(s).")
        if s.tackles_won > 0:
            lines.append(f"{s.tackles_won} tackle(s) won.")
    elif slot in ("CAM", "RW", "LW", "RM", "LM"):
        if s.goals_scored > 0 or s.assists > 0:
            lines.append(f"{s.goals_scored}G + {s.assists}A.")
        if s.dribbles_completed > 0:
            lines.append(f"{s.dribbles_completed} dribble(s) completed.")
    elif slot in ("ST", "CF"):
        lines.append(f"{s.goals_scored} goal(s), {s.shots_on_target} shot(s) on target.")

    if result_str:
        lines.append(f"Part of a {result_str} team.")

    return " ".join(lines) if lines else f"Best performer at {slot} this matchweek."


def save_totw_selection(matchweek: int, totw: TOTWSelection) -> Path:
    """Save the full TOTW selection to output/matchweek-{N}/analysis/players.json."""
    out_dir = matchweek_analysis_dir(matchweek)
    path = out_dir / "players.json"
    save_json_cache(path, totw.model_dump())
    return path


def print_totw_table(totw: TOTWSelection) -> None:
    """Print the TOTW selection as a formatted table."""
    print(f"\n{'='*75}")
    print(f"PREMIER LEAGUE TEAM OF THE WEEK — MATCHWEEK {totw.matchweek}")
    print(f"{'='*75}")
    print(f"Formation: {totw.formation.formation}")
    print(f"Rationale: {totw.formation.rationale}")
    print()
    print(f"{'Pos':<6} {'Player':<28} {'Team':<22} {'Rating':>6}  Key Stat")
    print("-" * 95)
    for tp in totw.players:
        p = tp.player
        rating = p.stats.games.rating or "N/A"
        stat_str = tp.key_stat[:35] + "..." if len(tp.key_stat) > 35 else tp.key_stat
        print(f"{tp.position_slot:<6} {p.name:<28} {p.team_name:<22} {rating:>6}  {stat_str}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/player_evaluator.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"Evaluating players for matchweek {matchweek}...")

    # Load formation
    formation_path = matchweek_analysis_dir(matchweek) / "formation.json"
    formation_data = load_json_cache(formation_path)
    if not formation_data:
        print("No formation analysis found. Run formation_analyzer.py first.")
        sys.exit(1)

    formation = SelectedFormation(**formation_data)

    # Load all players
    all_players = load_all_players(matchweek)
    print(f"Loaded {len(all_players)} players from cache.")

    # Select TOTW
    selected = select_players_for_formation(formation, all_players)

    totw = TOTWSelection(
        matchweek=matchweek,
        formation=formation,
        players=selected,
    )

    out_path = save_totw_selection(matchweek, totw)
    print_totw_table(totw)
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
