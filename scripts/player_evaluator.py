"""
Player Evaluator for the EPL TOTW Builder.

Loads cached player stats for a matchweek, applies enhanced position-specific
ranking criteria, and produces a top-3 shortlist per position slot.

Analyst subagents then review the shortlists and pick the final top 1 per slot.
The merge_analyst_selections.py script assembles the final players.json.

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
    Shortlist,
    ShortlistCandidate,
    ShortlistSlot,
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
# Each returns a tuple for sort (descending). Card penalty is always last.
# Key principle: every position uses stats it actually produces — no zeros.
# ---------------------------------------------------------------------------

def score_gk(p: Player) -> tuple:
    """GK: saves, clean sheet, penalty saves, goals conceded (inverted), rating."""
    return (
        p.stats.saves,
        1 if p.stats.clean_sheet else 0,
        p.stats.penalty_saves,
        -(p.stats.goals.conceded or 0),
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_cb(p: Player) -> tuple:
    """CB: defensive actions (tackles+intercepts), clearances, aerial dominance, rating."""
    def_actions = p.stats.tackles_won + p.stats.interceptions
    return (
        def_actions,
        p.stats.clearances,
        (p.stats.tackles.blocks or 0) + p.stats.aerial_duels_won,
        p.stats.aerial_won_rate,
        p.stats.duels_won,
        p.stats.pass_accuracy,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_fb(p: Player) -> tuple:
    """RB/LB: defensive + attacking dual role, crosses, xA."""
    attacking = p.stats.key_passes + (p.stats.assists * 2) + p.stats.xa_value
    return (
        p.stats.defensive_actions + attacking,
        p.stats.accurate_crosses,
        p.stats.dribbles_completed + p.stats.aerial_duels_won,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_wb(p: Player) -> tuple:
    """LWB/RWB: attacking weighted more heavily, crosses, xA."""
    attacking = (p.stats.assists * 3) + (p.stats.key_passes * 2) + (p.stats.xa_value * 2)
    return (
        attacking,
        p.stats.accurate_crosses,
        p.stats.defensive_actions,
        p.stats.dribbles_completed,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_cdm(p: Player) -> tuple:
    """CDM: tackles + interceptions primary, total passes as work-rate indicator."""
    return (
        p.stats.tackles_won + p.stats.interceptions,
        p.stats.clearances + p.stats.duels_won,
        p.stats.total_passes,
        p.stats.pass_accuracy,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_cm(p: Player) -> tuple:
    """CM: key passes + goal contributions, xA, total passes, accuracy."""
    return (
        p.stats.key_passes + p.stats.goal_contributions,
        p.stats.xa_value,
        p.stats.total_passes,
        p.stats.pass_accuracy,
        p.stats.tackles_won,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_cam(p: Player) -> tuple:
    """CAM: creative output, xA+xG, dribble quality, shots on target."""
    return (
        p.stats.key_passes + p.stats.goal_contributions,
        p.stats.xa_value + p.stats.xg_value,
        p.stats.dribbles_completed + p.stats.dribble_success_rate,
        p.stats.shots_on_target,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_winger(p: Player) -> tuple:
    """RW/LW/RM/LM: goals+assists, xG+xA, dribble quality, key passes, crosses."""
    return (
        p.stats.goals_scored + p.stats.assists,
        p.stats.xg_value + p.stats.xa_value,
        p.stats.dribbles_completed + p.stats.dribble_success_rate,
        p.stats.key_passes,
        p.stats.accurate_crosses,
        p.stats.shots_on_target,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


def score_st(p: Player) -> tuple:
    """ST/CF: goals primary, xG, shot volume, conversion, aerial dominance."""
    return (
        p.stats.goals_scored,
        p.stats.shots_on_target,
        p.stats.xg_value,
        p.stats.shot_conversion,
        p.stats.assists,
        p.stats.aerial_duels_won + p.stats.aerial_won_rate,
        p.stats.rating_float,
        p.stats.card_penalty,
    )


# ---------------------------------------------------------------------------
# Position slot → score function + eligible API position codes
# ---------------------------------------------------------------------------

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
    "RM":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "LM":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "RW":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "LW":  {"score_fn": score_winger, "api_pos": {"M", "F"}},
    "ST":  {"score_fn": score_st,     "api_pos": {"F", "M"}},
    "CF":  {"score_fn": score_st,     "api_pos": {"F", "M"}},
}

SLOT_COMPATIBILITY: dict[str, dict[str, list[str]]] = {
    "GK":  {"primary": ["GK"],               "flexible": []},
    "RB":  {"primary": ["RB", "RWB"],        "flexible": ["CB", "LB"]},
    "CB":  {"primary": ["CB"],               "flexible": ["RB", "LB", "CDM"]},
    "LB":  {"primary": ["LB", "LWB"],        "flexible": ["CB", "RB"]},
    "RWB": {"primary": ["RWB", "RB", "RM"],  "flexible": ["CB"]},
    "LWB": {"primary": ["LWB", "LB", "LM"],  "flexible": ["CB"]},
    "CDM": {"primary": ["CDM"],              "flexible": ["CM", "CB"]},
    "CM":  {"primary": ["CM", "CDM", "CAM"], "flexible": ["RM", "LM"]},
    "CAM": {"primary": ["CAM", "CM"],        "flexible": ["RM", "LM", "ST"]},
    "RM":  {"primary": ["RM", "RW", "RWB"],  "flexible": ["CM", "LM"]},
    "LM":  {"primary": ["LM", "LW", "LWB"],  "flexible": ["CM", "RM"]},
    "RW":  {"primary": ["RW", "RM"],         "flexible": ["LW", "CAM"]},
    "LW":  {"primary": ["LW", "LM"],         "flexible": ["RW", "CAM"]},
    "ST":  {"primary": ["ST", "CF"],         "flexible": ["CAM", "RW", "LW"]},
    "CF":  {"primary": ["CF", "ST"],         "flexible": ["CAM"]},
}

FLEXIBLE_API_POS: dict[str, set[str]] = {
    "CDM": {"D"},
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
    team_side: str,
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
            accurate_crosses=passes_raw.get("accurate_crosses"),
        ),
        tackles=PlayerTackles(
            total=tackles_raw.get("total"),
            blocks=tackles_raw.get("blocks"),
            interceptions=tackles_raw.get("interceptions"),
            clearances=tackles_raw.get("clearances"),
        ),
        duels=PlayerDuels(
            total=duels_raw.get("total"),
            won=duels_raw.get("won"),
            aerial_won=duels_raw.get("aerial_won"),
            aerial_lost=duels_raw.get("aerial_lost"),
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
        xg=stats_raw.get("xg"),
        xa=stats_raw.get("xa"),
    )

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
        nationality=p.get("nationality", ""),
        country_code=p.get("country_code", "xx") or "xx",
        position_code=position,
        specific_position=p.get("specific_position") or None,
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
            side = "home" if team_raw["id"] == home_team["id"] else "away"

            for player_raw in team_data.get("players", []):
                p = _parse_player_from_cache(
                    player_raw, team_raw, fixture_id, fixture_winner, side
                )
                if p:
                    all_players.append(p)

    return all_players


def _get_candidates(
    position_slot: str,
    all_players: list[Player],
    exclude_ids: set[int],
) -> list[Player]:
    """Return eligible candidates for a slot using 4-tier fallback."""
    config = POSITION_CONFIG.get(position_slot, {})
    api_pos = config.get("api_pos", set())
    flex_api_pos = FLEXIBLE_API_POS.get(position_slot, set())
    compat = SLOT_COMPATIBILITY.get(position_slot, {"primary": [], "flexible": []})
    primary_specific = set(compat["primary"])
    flexible_specific = set(compat["flexible"])

    def eligible(p: Player) -> bool:
        return p.player_id not in exclude_ids and p.is_eligible

    # Tier 1: exact specific_position match
    candidates = [p for p in all_players if eligible(p) and p.specific_position in primary_specific]
    if candidates:
        return candidates

    # Tier 2: flexible specific_position match
    candidates = [p for p in all_players if eligible(p) and p.specific_position in flexible_specific]
    if candidates:
        return candidates

    # Tier 3: broad API position code
    candidates = [p for p in all_players if eligible(p) and p.position_code in api_pos]
    if candidates:
        return candidates

    # Tier 4: include flexible api_pos codes
    candidates = [p for p in all_players if eligible(p) and p.position_code in (api_pos | flex_api_pos)]
    if candidates:
        return candidates

    # Fallback: anyone with most minutes
    return [p for p in all_players if p.player_id not in exclude_ids]


def _sort_candidates(candidates: list[Player], score_fn) -> list[Player]:
    """Sort candidates by score + win bonus + minutes."""
    def sort_key(p: Player):
        score = score_fn(p)
        win_bonus = 1 if p.fixture_result == "win" else 0
        minutes = p.stats.minutes_played
        return score + (win_bonus,) + (minutes,)

    return sorted(candidates, key=sort_key, reverse=True)


def _build_stats_snapshot(player: Player, slot: str) -> dict:
    """Return a position-appropriate flat dict of relevant stats for analyst display."""
    s = player.stats
    base = {"rating": s.rating_float, "minutes": s.minutes_played, "result": player.fixture_result}

    if slot == "GK":
        return {**base,
            "saves": s.saves,
            "conceded": s.goals.conceded,
            "penalty_saves": s.penalty_saves,
            "clean_sheet": s.clean_sheet,
            "pass_accuracy": s.pass_accuracy,
        }
    elif slot == "CB":
        return {**base,
            "tackles_won": s.tackles_won,
            "interceptions": s.interceptions,
            "clearances": s.clearances,
            "blocks": s.tackles.blocks or 0,
            "aerial_won": s.aerial_duels_won,
            "aerial_won_rate": s.aerial_won_rate,
            "duels_won": s.duels_won,
            "pass_accuracy": s.pass_accuracy,
        }
    elif slot in ("RB", "LB"):
        return {**base,
            "tackles_won": s.tackles_won,
            "interceptions": s.interceptions,
            "key_passes": s.key_passes,
            "assists": s.assists,
            "xa": s.xa_value,
            "accurate_crosses": s.accurate_crosses,
            "dribbles": s.dribbles_completed,
            "aerial_won": s.aerial_duels_won,
        }
    elif slot in ("RWB", "LWB"):
        return {**base,
            "assists": s.assists,
            "key_passes": s.key_passes,
            "xa": s.xa_value,
            "accurate_crosses": s.accurate_crosses,
            "dribbles": s.dribbles_completed,
            "tackles_won": s.tackles_won,
            "interceptions": s.interceptions,
        }
    elif slot == "CDM":
        return {**base,
            "tackles_won": s.tackles_won,
            "interceptions": s.interceptions,
            "clearances": s.clearances,
            "duels_won": s.duels_won,
            "total_passes": s.total_passes,
            "pass_accuracy": s.pass_accuracy,
        }
    elif slot == "CM":
        return {**base,
            "key_passes": s.key_passes,
            "goals": s.goals_scored,
            "assists": s.assists,
            "xa": s.xa_value,
            "total_passes": s.total_passes,
            "pass_accuracy": s.pass_accuracy,
            "tackles_won": s.tackles_won,
        }
    elif slot == "CAM":
        return {**base,
            "key_passes": s.key_passes,
            "goals": s.goals_scored,
            "assists": s.assists,
            "xa": s.xa_value,
            "xg": s.xg_value,
            "dribbles": s.dribbles_completed,
            "dribble_success_rate": s.dribble_success_rate,
            "shots_on_target": s.shots_on_target,
        }
    elif slot in ("RW", "LW", "RM", "LM"):
        return {**base,
            "goals": s.goals_scored,
            "assists": s.assists,
            "xg": s.xg_value,
            "xa": s.xa_value,
            "dribbles": s.dribbles_completed,
            "dribble_success_rate": s.dribble_success_rate,
            "key_passes": s.key_passes,
            "accurate_crosses": s.accurate_crosses,
            "shots_on_target": s.shots_on_target,
        }
    elif slot in ("ST", "CF"):
        return {**base,
            "goals": s.goals_scored,
            "shots_on_target": s.shots_on_target,
            "xg": s.xg_value,
            "shot_conversion": s.shot_conversion,
            "assists": s.assists,
            "aerial_won": s.aerial_duels_won,
            "aerial_won_rate": s.aerial_won_rate,
            "dribbles": s.dribbles_completed,
        }
    else:
        return {**base,
            "goals": s.goals_scored,
            "assists": s.assists,
            "key_passes": s.key_passes,
            "tackles_won": s.tackles_won,
        }


def _compute_display_score(player: Player, slot: str) -> float:
    """Rating-anchored composite score for shortlist display."""
    s = player.stats
    base = s.rating_float + s.card_penalty

    bonuses: dict[str, float] = {
        "GK":  s.saves * 0.3 + (0.5 if s.clean_sheet else 0) + s.penalty_saves * 0.5,
        "CB":  (s.tackles_won + s.interceptions) * 0.15 + s.clearances * 0.1 + s.aerial_won_rate * 0.3,
        "RB":  s.defensive_actions * 0.1 + s.assists * 0.4 + s.key_passes * 0.15 + s.xa_value * 0.2,
        "LB":  s.defensive_actions * 0.1 + s.assists * 0.4 + s.key_passes * 0.15 + s.xa_value * 0.2,
        "RWB": s.assists * 0.5 + s.key_passes * 0.2 + s.xa_value * 0.3 + s.accurate_crosses * 0.1,
        "LWB": s.assists * 0.5 + s.key_passes * 0.2 + s.xa_value * 0.3 + s.accurate_crosses * 0.1,
        "CDM": (s.tackles_won + s.interceptions) * 0.2 + s.total_passes * 0.005,
        "CM":  s.key_passes * 0.2 + s.goal_contributions * 0.4 + s.xa_value * 0.2,
        "CAM": s.key_passes * 0.25 + s.goal_contributions * 0.4 + s.xa_value * 0.25,
        "RM":  s.goals_scored * 0.6 + s.assists * 0.4 + s.xg_value * 0.2 + s.xa_value * 0.15,
        "LM":  s.goals_scored * 0.6 + s.assists * 0.4 + s.xg_value * 0.2 + s.xa_value * 0.15,
        "RW":  s.goals_scored * 0.6 + s.assists * 0.4 + s.xg_value * 0.2 + s.xa_value * 0.15,
        "LW":  s.goals_scored * 0.6 + s.assists * 0.4 + s.xg_value * 0.2 + s.xa_value * 0.15,
        "ST":  s.goals_scored * 0.7 + s.shots_on_target * 0.1 + s.xg_value * 0.2,
        "CF":  s.goals_scored * 0.7 + s.shots_on_target * 0.1 + s.xg_value * 0.2,
    }

    return round(base + bonuses.get(slot, 0.0), 2)


def build_shortlists(
    matchweek: int,
    formation: SelectedFormation,
    all_players: list[Player],
) -> Shortlist:
    """
    Build a top-3 shortlist per position slot.
    Players can appear in multiple shortlists — analysts deduplicate.
    """
    positions = formation.positions
    slots: list[ShortlistSlot] = []

    for slot_idx, position_slot in enumerate(positions):
        config = POSITION_CONFIG.get(position_slot)
        if not config:
            continue

        score_fn = config["score_fn"]
        # No used_ids exclusion here — analysts handle deduplication
        candidates = _get_candidates(position_slot, all_players, exclude_ids=set())
        candidates = _sort_candidates(candidates, score_fn)

        top3 = candidates[:3]
        shortlist_candidates = []
        for rank_i, cand in enumerate(top3, 1):
            shortlist_candidates.append(ShortlistCandidate(
                rank=rank_i,
                player_name=cand.name,
                team=cand.team_name,
                player_id=cand.player_id,
                score=_compute_display_score(cand, position_slot),
                fixture_id=cand.fixture_id,
                fixture_result=cand.fixture_result or "unknown",
                stats=_build_stats_snapshot(cand, position_slot),
            ))

        slots.append(ShortlistSlot(
            slot_index=slot_idx,
            position=position_slot,
            candidates=shortlist_candidates,
        ))

    return Shortlist(
        matchweek=matchweek,
        formation=formation.formation,
        slots=slots,
    )


def _build_key_stat(player: Player, slot: str) -> str:
    """Build a concise key stat string for a player at a position."""
    s = player.stats
    parts = []

    if slot == "GK":
        if s.saves > 0:
            parts.append(f"{s.saves} save{'s' if s.saves != 1 else ''}")
        if s.penalty_saves > 0:
            parts.append(f"{s.penalty_saves} penalty save{'s' if s.penalty_saves != 1 else ''}")
        if s.clean_sheet:
            parts.append("clean sheet")
        if s.goals.conceded is not None:
            parts.append(f"{s.goals.conceded} conceded")

    elif slot in ("CB", "RB", "LB", "RWB", "LWB"):
        if s.tackles_won > 0:
            parts.append(f"{s.tackles_won} tackle{'s' if s.tackles_won != 1 else ''}")
        if s.interceptions > 0:
            parts.append(f"{s.interceptions} interception{'s' if s.interceptions != 1 else ''}")
        if s.clearances > 0:
            parts.append(f"{s.clearances} clearance{'s' if s.clearances != 1 else ''}")
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")

    elif slot == "CDM":
        if s.tackles_won > 0:
            parts.append(f"{s.tackles_won} tackle{'s' if s.tackles_won != 1 else ''}")
        if s.interceptions > 0:
            parts.append(f"{s.interceptions} interception{'s' if s.interceptions != 1 else ''}")
        if s.total_passes > 0:
            parts.append(f"{s.total_passes} passes")

    elif slot in ("CM", "CAM"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")
        if s.key_passes > 0:
            parts.append(f"{s.key_passes} key pass{'es' if s.key_passes != 1 else ''}")
        if s.xa_value > 0:
            parts.append(f"xA {s.xa_value:.2f}")

    elif slot in ("RW", "LW", "RM", "LM"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")
        if s.xg_value > 0:
            parts.append(f"xG {s.xg_value:.2f}")
        if s.dribbles_completed > 0:
            parts.append(f"{s.dribbles_completed} dribble{'s' if s.dribbles_completed != 1 else ''}")

    elif slot in ("ST", "CF"):
        if s.goals_scored > 0:
            parts.append(f"{s.goals_scored} goal{'s' if s.goals_scored != 1 else ''}")
        if s.shots_on_target > 0:
            parts.append(f"{s.shots_on_target} shot{'s' if s.shots_on_target != 1 else ''} on target")
        if s.xg_value > 0:
            parts.append(f"xG {s.xg_value:.2f}")
        if s.assists > 0:
            parts.append(f"{s.assists} assist{'s' if s.assists != 1 else ''}")

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
        if s.penalty_saves > 0:
            lines.append(f"Saved {s.penalty_saves} penalty/penalties.")
        if s.clean_sheet:
            lines.append("Kept a clean sheet.")
    elif slot in ("CB", "RB", "LB", "RWB", "LWB"):
        if s.defensive_actions > 0:
            lines.append(f"{s.defensive_actions} combined tackles + interceptions.")
        if s.clearances > 0:
            lines.append(f"{s.clearances} clearance(s).")
    elif slot == "CDM":
        if s.tackles_won + s.interceptions > 0:
            lines.append(f"{s.tackles_won + s.interceptions} defensive actions.")
        if s.total_passes > 0:
            lines.append(f"{s.total_passes} passes ({s.pass_accuracy:.0f}% accuracy).")
    elif slot in ("CM", "CAM"):
        if s.key_passes > 0:
            lines.append(f"{s.key_passes} key passes created.")
        if s.goal_contributions > 0:
            lines.append(f"{s.goal_contributions} goal contribution(s).")
        if s.xa_value > 0:
            lines.append(f"xA of {s.xa_value:.2f}.")
    elif slot in ("RW", "LW", "RM", "LM"):
        if s.goals_scored > 0 or s.assists > 0:
            lines.append(f"{s.goals_scored}G + {s.assists}A.")
        if s.xg_value > 0:
            lines.append(f"xG of {s.xg_value:.2f}.")
        if s.dribbles_completed > 0:
            lines.append(f"{s.dribbles_completed} dribble(s) completed.")
    elif slot in ("ST", "CF"):
        lines.append(f"{s.goals_scored} goal(s), {s.shots_on_target} shot(s) on target.")
        if s.xg_value > 0:
            lines.append(f"xG of {s.xg_value:.2f}.")

    if result_str:
        lines.append(f"Part of a {result_str} team.")

    return " ".join(lines) if lines else f"Best performer at {slot} this matchweek."


def save_totw_selection(matchweek: int, totw: TOTWSelection) -> Path:
    """Save the full TOTW selection to output/matchweek-{N}/analysis/players.json."""
    out_dir = matchweek_analysis_dir(matchweek)
    path = out_dir / "players.json"
    save_json_cache(path, totw.model_dump())
    return path


def print_shortlist_table(shortlist: Shortlist) -> None:
    """Print the shortlists as a formatted table."""
    print(f"\n{'='*80}")
    print(f"PREMIER LEAGUE TOTW SHORTLISTS — MATCHWEEK {shortlist.matchweek}")
    print(f"Formation: {shortlist.formation}")
    print(f"{'='*80}")

    for slot in shortlist.slots:
        print(f"\n[{slot.slot_index}] {slot.position}")
        print(f"  {'#':<3} {'Player':<28} {'Team':<22} {'Score':>6}  Key Stats")
        print(f"  {'-'*80}")
        for c in slot.candidates:
            stat_items = [f"{k}={v}" for k, v in c.stats.items()
                          if k not in ("rating", "minutes", "result") and v not in (None, 0, 0.0, False)]
            stat_str = ", ".join(stat_items[:4])
            print(f"  {c.rank:<3} {c.player_name:<28} {c.team:<22} {c.score:>6.2f}  {stat_str}")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/player_evaluator.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"Building shortlists for matchweek {matchweek}...")

    formation_path = matchweek_analysis_dir(matchweek) / "formation.json"
    formation_data = load_json_cache(formation_path)
    if not formation_data:
        print("No formation analysis found. Run formation_analyzer.py first.")
        sys.exit(1)

    formation = SelectedFormation(**formation_data)

    all_players = load_all_players(matchweek)
    print(f"Loaded {len(all_players)} players from cache.")

    shortlist = build_shortlists(matchweek, formation, all_players)

    shortlist_path = matchweek_analysis_dir(matchweek) / "shortlists.json"
    save_json_cache(shortlist_path, shortlist.model_dump())

    # Write empty players.json placeholder — analysts populate it via merge script
    empty_totw = TOTWSelection(matchweek=matchweek, formation=formation, players=[])
    save_totw_selection(matchweek, empty_totw)

    print_shortlist_table(shortlist)
    print(f"Shortlists saved to: {shortlist_path}")
    print(f"Analysts: review shortlists and write analyst_1/2/3.json, then run merge_analyst_selections.py")


if __name__ == "__main__":
    main()
