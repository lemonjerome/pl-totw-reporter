"""
soccerdata_client.py — Multi-source data client for EPL TOTW Builder (2025-26 season).

Data sources:
- FPL API (fantasy.premierleague.com): Matchweek fixtures, scores, team IDs. No key needed.
- Understat (via soccerdata): Player match stats — goals, assists, key_passes, minutes, shots, xg.
- ESPN (via soccerdata): Player lineup — saves, goals_conceded, shots_on_target, formation_place.

No API key required. soccerdata handles its own caching in ~/soccerdata/data/.
This script adds a second cache layer in data/2025-26/matchweek-{N}/ (same layout as api_football.py).

CLI:
  python scripts/soccerdata_client.py check-budget
  python scripts/soccerdata_client.py check-status 28
  python scripts/soccerdata_client.py fetch-round 28
  python scripts/soccerdata_client.py fetch-players 28
  python scripts/soccerdata_client.py fetch-lineups 28
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    cache_exists,
    load_json_cache,
    save_json_cache,
    matchweek_data_dir,
    get_country_code,
)
from data_models import (
    Fixture, TeamInfo, Score, FixtureStatus,
    Player, PlayerStats, PlayerGames, PlayerGoals, PlayerShots,
    PlayerPasses, PlayerTackles, PlayerDuels, PlayerDribbles,
    PlayerCards,
)

# ---------------------------------------------------------------------------
# Season / league constants
# ---------------------------------------------------------------------------

# Understat uses start year: 2025 → 2025-26 season (internally "2526")
UNDERSTAT_SEASON = 2025

# ESPN uses end year: 2026 → 2025-26 season (internally "2627")
ESPN_SEASON = 2026

# FPL API base (no key needed, public)
FPL_BASE = "https://fantasy.premierleague.com/api"

# ---------------------------------------------------------------------------
# Team name normalization: FPL / Understat / ESPN → canonical name
# ---------------------------------------------------------------------------

# FPL team names → canonical
FPL_TO_CANONICAL: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Burnley": "Burnley",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Leeds": "Leeds",
    "Liverpool": "Liverpool",
    "Man City": "Man City",
    "Man Utd": "Man Utd",
    "Newcastle": "Newcastle",
    "Nott'm Forest": "Nottm Forest",
    "Sunderland": "Sunderland",
    "Spurs": "Spurs",
    "West Ham": "West Ham",
    "Wolves": "Wolves",
}

# Understat team names → canonical
UNDERSTAT_TO_CANONICAL: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Burnley": "Burnley",
    "Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Leeds United": "Leeds",
    "Liverpool": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottm Forest",
    "Sunderland": "Sunderland",
    "Tottenham": "Spurs",
    "West Ham": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}

# ESPN team names → canonical
ESPN_TO_CANONICAL: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Burnley": "Burnley",
    "AFC Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton & Hove Albion": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Leeds United": "Leeds",
    "Liverpool": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottm Forest",
    "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur": "Spurs",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
}


def _normalize_team(name: str, mapping: dict[str, str]) -> str:
    """Map team name to canonical form. Falls back to the original name."""
    return mapping.get(name, name)


# ---------------------------------------------------------------------------
# FPL team registry (loaded once from bootstrap-static)
# ---------------------------------------------------------------------------

_FPL_TEAMS: dict[int, dict] = {}   # id → {name, canonical, short_name, code}

# FPL player photo lookup: (normalized_full_name, fpl_team_id) → photo_url
_FPL_PLAYER_PHOTOS: dict[tuple[str, int], str] = {}
_FPL_PLAYER_PHOTOS_LOADED = False


def _load_fpl_teams() -> dict[int, dict]:
    global _FPL_TEAMS
    if _FPL_TEAMS:
        return _FPL_TEAMS

    cache_path = Path(__file__).parent.parent / "data" / "fpl_teams.json"
    cached = load_json_cache(cache_path)
    if cached:
        _FPL_TEAMS = {int(k): v for k, v in cached.items()}
        return _FPL_TEAMS

    print("  [FPL] Loading team registry from bootstrap-static...")
    url = f"{FPL_BASE}/bootstrap-static/"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())

    for t in data["teams"]:
        _FPL_TEAMS[t["id"]] = {
            "name": t["name"],
            "canonical": FPL_TO_CANONICAL.get(t["name"], t["name"]),
            "short_name": t["short_name"],
            "code": t.get("code", t["id"]),
        }

    save_json_cache(cache_path, {str(k): v for k, v in _FPL_TEAMS.items()})
    return _FPL_TEAMS


def _load_fpl_player_photos() -> None:
    """Load FPL player photo lookup from bootstrap-static (fetched once with teams)."""
    global _FPL_PLAYER_PHOTOS, _FPL_PLAYER_PHOTOS_LOADED
    if _FPL_PLAYER_PHOTOS_LOADED:
        return

    cache_path = Path(__file__).parent.parent / "data" / "fpl_player_photos.json"
    cached = load_json_cache(cache_path)
    if cached:
        _FPL_PLAYER_PHOTOS = {(k.split("|")[0], int(k.split("|")[1])): v for k, v in cached.items()}
        _FPL_PLAYER_PHOTOS_LOADED = True
        return

    print("  [FPL] Loading player photo registry from bootstrap-static...")
    url = f"{FPL_BASE}/bootstrap-static/"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read())

    serializable: dict[str, str] = {}
    for p in data.get("elements", []):
        code = p.get("code")
        if not code:
            continue
        photo_url = f"https://resources.premierleague.com/premierleague/photos/players/250x250/p{code}.png"
        team_id = p.get("team", 0)
        first = p.get("first_name", "").strip().lower()
        second = p.get("second_name", "").strip().lower()
        web_name = p.get("web_name", "").strip().lower()
        full_name = f"{first} {second}".strip()
        # Last word of second_name handles compound surnames ("Borges Fernandes" → "fernandes")
        last_surname = second.split()[-1] if second else ""
        candidates = {full_name, web_name, last_surname} - {""}
        for key_name in candidates:
            key = f"{key_name}|{team_id}"
            # setdefault: first match wins (prevents clobbering unique keys with common surnames)
            _FPL_PLAYER_PHOTOS.setdefault((key_name, team_id), photo_url)
            serializable.setdefault(key, photo_url)

    save_json_cache(cache_path, serializable)
    _FPL_PLAYER_PHOTOS_LOADED = True


def _fpl_player_photo(player_name: str, fpl_team_id: int) -> str:
    """Return official PL player photo URL by matching name + team. Falls back to ''."""
    _load_fpl_player_photos()
    name_lower = player_name.strip().lower()
    # Try full name match
    photo = _FPL_PLAYER_PHOTOS.get((name_lower, fpl_team_id), "")
    if photo:
        return photo
    # Try last name only
    last = name_lower.split()[-1] if name_lower else ""
    if last:
        photo = _FPL_PLAYER_PHOTOS.get((last, fpl_team_id), "")
    return photo


def _team_badge_url(fpl_team_id: int) -> str:
    """FPL CDN badge URL for a team."""
    teams = _load_fpl_teams()
    code = teams.get(fpl_team_id, {}).get("code", fpl_team_id)
    return f"https://resources.premierleague.com/premierleague/badges/rb/t{code}.svg"


def _fpl_team_name(fpl_team_id: int) -> str:
    teams = _load_fpl_teams()
    return teams.get(fpl_team_id, {}).get("name", f"Team {fpl_team_id}")


def _fpl_canonical_name(fpl_team_id: int) -> str:
    teams = _load_fpl_teams()
    return teams.get(fpl_team_id, {}).get("canonical", f"Team {fpl_team_id}")


# ---------------------------------------------------------------------------
# Integer ID helpers (FPL uses ints natively; generate hash-IDs for players)
# ---------------------------------------------------------------------------

def _player_id(name: str, team: str) -> int:
    """Generate a stable integer player ID from name + team."""
    key = f"{name.lower().strip()}|{team.lower().strip()}"
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)


def _player_photo_url(player_name: str, fpl_team_id: int, understat_player_id: Optional[int]) -> str:
    """Best-effort player photo URL. Prefers official PL CDN photo, falls back to Understat."""
    fpl_photo = _fpl_player_photo(player_name, fpl_team_id)
    if fpl_photo:
        return fpl_photo
    if understat_player_id:
        return f"https://understat.com/images/player/{understat_player_id}.jpg"
    return ""


# ---------------------------------------------------------------------------
# FPL API helpers
# ---------------------------------------------------------------------------

def _fpl_get(path: str) -> dict | list:
    """Simple GET request to FPL public API."""
    url = f"{FPL_BASE}/{path}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def _fetch_fpl_fixtures(matchweek: int) -> list[dict]:
    """Fetch raw FPL fixture data for a matchweek."""
    return _fpl_get(f"fixtures/?event={matchweek}")


# ---------------------------------------------------------------------------
# Fixture parsing (FPL → Pydantic Fixture)
# ---------------------------------------------------------------------------

def _fpl_to_api_football_fixture(raw: dict) -> dict:
    """Convert a raw FPL fixture dict to API-Football-compatible format for caching."""
    fpl_id = raw["id"]
    matchweek = raw["event"]
    home_id = raw["team_h"]
    away_id = raw["team_a"]

    home_score = raw.get("team_h_score")
    away_score = raw.get("team_a_score")
    finished = raw.get("finished", False)
    started = raw.get("started", False)

    if finished:
        status_short, status_long = "FT", "Match Finished"
    elif started:
        status_short, status_long = "1H", "In Progress"
    else:
        status_short, status_long = "NS", "Not Started"

    home_name = _fpl_team_name(home_id)
    away_name = _fpl_team_name(away_id)
    home_winner = None
    away_winner = None
    if finished and home_score is not None and away_score is not None:
        home_winner = home_score > away_score
        away_winner = away_score > home_score

    return {
        "fixture": {
            "id": fpl_id,
            "date": raw.get("kickoff_time", ""),
            "status": {"short": status_short, "long": status_long, "elapsed": raw.get("minutes")},
        },
        "league": {"round": f"Regular Season - {matchweek}"},
        "teams": {
            "home": {"id": home_id, "name": home_name, "logo": _team_badge_url(home_id), "winner": home_winner},
            "away": {"id": away_id, "name": away_name, "logo": _team_badge_url(away_id), "winner": away_winner},
        },
        "goals": {"home": home_score, "away": away_score},
        "score": {"fulltime": {"home": home_score, "away": away_score}},
    }


def _parse_api_football_fixture(raw: dict) -> Fixture:
    """Convert API-Football-format fixture dict to a Pydantic Fixture model."""
    fix = raw["fixture"]
    teams = raw["teams"]
    score = raw.get("score", {})
    ft = score.get("fulltime", {})
    matchweek_str = raw["league"]["round"]

    return Fixture(
        fixture_id=fix["id"],
        date=fix["date"],
        round=matchweek_str,
        home_team=TeamInfo(
            id=teams["home"]["id"],
            name=teams["home"]["name"],
            logo=teams["home"]["logo"],
        ),
        away_team=TeamInfo(
            id=teams["away"]["id"],
            name=teams["away"]["name"],
            logo=teams["away"]["logo"],
        ),
        score=Score(home=ft.get("home"), away=ft.get("away")),
        status=FixtureStatus(
            short=fix["status"]["short"],
            long=fix["status"]["long"],
            elapsed=fix["status"].get("elapsed"),
        ),
    )


# ---------------------------------------------------------------------------
# Fetch and cache fixtures
# ---------------------------------------------------------------------------

def fetch_fixtures(matchweek: int) -> list[Fixture]:
    """
    Fetch fixtures for a matchweek from FPL API.
    Caches to fixtures.json in API-Football-compatible format
    so formation_analyzer.py and player_evaluator.py work unmodified.
    """
    data_dir = matchweek_data_dir(matchweek)
    cache_path = data_dir / "fixtures.json"

    if cache_exists(cache_path):
        raw_list = load_json_cache(cache_path)
        # Detect API-Football format vs old Pydantic dump
        if raw_list and "fixture" in raw_list[0]:
            print(f"  [Cache] Loading fixtures from {cache_path}")
            return [_parse_api_football_fixture(f) for f in raw_list]
        # Old Pydantic format — delete and re-fetch
        cache_path.unlink()

    _load_fpl_teams()
    print(f"  [FPL] Fetching matchweek {matchweek} fixtures...")
    raw_fixtures = _fetch_fpl_fixtures(matchweek)

    api_format = [_fpl_to_api_football_fixture(f) for f in raw_fixtures]
    save_json_cache(cache_path, api_format)
    print(f"  [Cache] Saved {len(api_format)} fixtures to {cache_path}")
    return [_parse_api_football_fixture(f) for f in api_format]


# ---------------------------------------------------------------------------
# Understat data loading
# ---------------------------------------------------------------------------

_understat_client = None
_understat_schedule = None


def _get_understat():
    global _understat_client
    if _understat_client is None:
        import soccerdata as sd
        _understat_client = sd.Understat(leagues="ENG-Premier League", seasons=UNDERSTAT_SEASON)
    return _understat_client


def _get_understat_schedule():
    global _understat_schedule
    if _understat_schedule is None:
        _understat_schedule = _get_understat().read_schedule()
    return _understat_schedule


def _find_understat_game_id(home_canonical: str, away_canonical: str, kickoff_date: str) -> Optional[int]:
    """Find Understat game_id by matching canonical team names + date."""
    sched = _get_understat_schedule()
    date_prefix = kickoff_date[:10]  # YYYY-MM-DD

    for _, row in sched.iterrows():
        u_home = UNDERSTAT_TO_CANONICAL.get(row["home_team"], row["home_team"])
        u_away = UNDERSTAT_TO_CANONICAL.get(row["away_team"], row["away_team"])
        u_date = str(row["date"])[:10]

        if u_home == home_canonical and u_away == away_canonical and u_date == date_prefix:
            return int(row["game_id"])

    return None


def _fetch_understat_player_stats(game_id: int) -> list[dict]:
    """Fetch per-player stats from Understat for one game."""
    u = _get_understat()
    df = u.read_player_match_stats([game_id])

    players = []
    for _, row in df.iterrows():
        players.append({
            "player_name": row.name[-1] if isinstance(row.name, tuple) else str(row.name),
            "team": row.name[-2] if isinstance(row.name, tuple) else "",
            "understat_player_id": int(row.get("player_id", 0)) if row.get("player_id") else None,
            "position": str(row.get("position", "")),
            "minutes": int(row.get("minutes", 0)),
            "goals": int(row.get("goals", 0) or 0),
            "assists": int(row.get("assists", 0) or 0),
            "shots": int(row.get("shots", 0) or 0),
            "key_passes": int(row.get("key_passes", 0) or 0),
            "xg": float(row.get("xg", 0.0) or 0.0),
            "xa": float(row.get("xa", 0.0) or 0.0),
            "yellow_cards": int(row.get("yellow_cards", 0) or 0),
            "red_cards": int(row.get("red_cards", 0) or 0),
        })
    return players


# ---------------------------------------------------------------------------
# ESPN data loading
# ---------------------------------------------------------------------------

_espn_client = None
_espn_schedule = None


def _get_espn():
    global _espn_client
    if _espn_client is None:
        import soccerdata as sd
        _espn_client = sd.ESPN(leagues="ENG-Premier League", seasons=ESPN_SEASON)
    return _espn_client


def _get_espn_schedule():
    global _espn_schedule
    if _espn_schedule is None:
        _espn_schedule = _get_espn().read_schedule()
    return _espn_schedule


def _find_espn_game_id(home_canonical: str, away_canonical: str, kickoff_date: str) -> Optional[int]:
    """Find ESPN game_id by matching canonical team names + date."""
    sched = _get_espn_schedule()
    date_prefix = kickoff_date[:10]

    for _, row in sched.iterrows():
        e_home = ESPN_TO_CANONICAL.get(row["home_team"], row["home_team"])
        e_away = ESPN_TO_CANONICAL.get(row["away_team"], row["away_team"])
        e_date = str(row["date"])[:10]

        if e_home == home_canonical and e_away == away_canonical and e_date == date_prefix:
            return int(row["game_id"])

    return None


def _fetch_espn_lineup(game_id: int) -> list[dict]:
    """Fetch per-player lineup stats from ESPN for one game."""
    e = _get_espn()
    df = e.read_lineup([game_id])

    players = []
    for idx, row in df.iterrows():
        # idx = (league, season, game, team, player)
        team = idx[-2] if isinstance(idx, tuple) else ""
        player_name = idx[-1] if isinstance(idx, tuple) else str(idx)

        sub_in = str(row.get("sub_in", ""))
        sub_out = str(row.get("sub_out", ""))
        minutes = _calc_minutes(sub_in, sub_out)

        players.append({
            "player_name": player_name,
            "team": team,
            "position": str(row.get("position", "")),
            "formation_place": int(row.get("formation_place", 0) or 0),
            "sub_in": sub_in,
            "sub_out": sub_out,
            "minutes": minutes,
            "is_home": bool(row.get("is_home", False)),
            "goals": int(row.get("total_goals", 0) or 0),
            "assists": int(row.get("goal_assists", 0) or 0),
            "shots_on_target": int(row.get("shots_on_target", 0) or 0),
            "total_shots": int(row.get("total_shots", 0) or 0),
            "saves": float(row.get("saves", 0) or 0),
            "goals_conceded": int(row.get("goals_conceded", 0) or 0),
            "yellow_cards": int(row.get("yellow_cards", 0) or 0),
            "red_cards": int(row.get("red_cards", 0) or 0),
            "fouls_committed": int(row.get("fouls_committed", 0) or 0),
        })
    return players


def _calc_minutes(sub_in: str, sub_out: str) -> int:
    """Compute minutes played from ESPN sub_in / sub_out strings."""
    try:
        start = 0 if sub_in == "start" else int(sub_in)
    except (ValueError, TypeError):
        start = 0

    try:
        end = 90 if sub_out in ("end", "") else int(sub_out)
    except (ValueError, TypeError):
        end = 0

    if start == 0 and end == 0 and sub_in not in ("start",):
        return 0  # didn't play
    return max(0, end - start)


# ---------------------------------------------------------------------------
# Position code mapping
# ---------------------------------------------------------------------------

UNDERSTAT_POS_TO_CODE: dict[str, str] = {
    "GK": "G", "GKP": "G",
    "DR": "D", "DL": "D", "DC": "D",
    "ML": "M", "MR": "M", "MC": "M", "DMC": "M", "AMC": "M",
    "FW": "F", "FWL": "F", "FWR": "F", "FWC": "F",
    "": "M",  # unknown → midfielder
}

ESPN_POS_TO_CODE: dict[str, str] = {
    "Goalkeeper": "G",
    "Center Back": "D", "Center Left Defender": "D", "Center Right Defender": "D",
    "Right Back": "D", "Left Back": "D", "Right Wing Back": "D", "Left Wing Back": "D",
    "Midfielder": "M", "Center Midfielder": "M", "Defensive Midfielder": "M",
    "Center Left Midfielder": "M", "Center Right Midfielder": "M",
    "Attacking Midfielder": "M", "Left Midfielder": "M", "Right Midfielder": "M",
    "Forward": "F", "Striker": "F", "Left Winger": "F", "Right Winger": "F",
    "Substitute": "M",  # fallback
}

ESPN_POS_TO_TACTICAL: dict[str, str] = {
    "Goalkeeper": "GK",
    "Center Back": "CB", "Center Left Defender": "CB", "Center Right Defender": "CB",
    "Right Back": "RB", "Left Back": "LB",
    "Right Wing Back": "RWB", "Left Wing Back": "LWB",
    "Defensive Midfielder": "CDM", "Center Midfielder": "CM",
    "Center Left Midfielder": "CM", "Center Right Midfielder": "CM",
    "Attacking Midfielder": "CAM", "Left Midfielder": "LM", "Right Midfielder": "RM",
    "Forward": "ST", "Striker": "ST",
    "Left Winger": "LW", "Right Winger": "RW",
    "Substitute": "",
}


# ---------------------------------------------------------------------------
# Merge Understat + ESPN stats into Player model
# ---------------------------------------------------------------------------

def _normalize_player_name(name: str) -> str:
    """Lowercase, strip accents naively for fuzzy matching."""
    return name.lower().strip()


def _build_player(
    player_name: str,
    team_canonical: str,
    team_fpl_id: int,
    team_fpl_logo: str,
    fixture_id: int,
    fixture_result: Optional[str],
    u_stats: Optional[dict],
    e_stats: Optional[dict],
) -> Player:
    """Merge Understat + ESPN stats into a Player Pydantic model."""

    # Minutes: prefer Understat (more accurate) then ESPN
    minutes = 0
    if u_stats:
        minutes = u_stats.get("minutes", 0)
    elif e_stats:
        minutes = e_stats.get("minutes", 0)

    # Position: ESPN position string → tactical code
    position_code = "M"
    tactical_position = ""
    if e_stats:
        espn_pos = e_stats.get("position", "")
        position_code = ESPN_POS_TO_CODE.get(espn_pos, "M")
        tactical_position = ESPN_POS_TO_TACTICAL.get(espn_pos, "")
    elif u_stats:
        u_pos = u_stats.get("position", "")
        position_code = UNDERSTAT_POS_TO_CODE.get(u_pos, "M")

    # Goals, assists — agree between sources, prefer Understat
    goals = 0
    assists = 0
    if u_stats:
        goals = u_stats.get("goals", 0)
        assists = u_stats.get("assists", 0)
    elif e_stats:
        goals = e_stats.get("goals", 0)
        assists = e_stats.get("assists", 0)

    # Shots — ESPN has shots_on_target; Understat has total shots
    shots_total = 0
    shots_on = 0
    if u_stats:
        shots_total = u_stats.get("shots", 0)
    if e_stats:
        shots_on = e_stats.get("shots_on_target", 0)
        if not shots_total:
            shots_total = e_stats.get("total_shots", 0)

    # Saves and goals_conceded — ESPN only
    saves = 0
    goals_conceded = None
    if e_stats:
        saves_raw = e_stats.get("saves", 0)
        saves = int(saves_raw) if saves_raw and str(saves_raw) != "nan" else 0
        goals_conceded = e_stats.get("goals_conceded", None)

    # Key passes — Understat only
    key_passes = 0
    if u_stats:
        key_passes = u_stats.get("key_passes", 0)

    # Cards — either source
    yellow = 0
    red = 0
    if u_stats:
        yellow = u_stats.get("yellow_cards", 0)
        red = u_stats.get("red_cards", 0)
    elif e_stats:
        yellow = e_stats.get("yellow_cards", 0)
        red = e_stats.get("red_cards", 0)

    # Formation place (for lineup)
    grid_pos = None
    if e_stats:
        fp = e_stats.get("formation_place", 0)
        if fp:
            grid_pos = f"1:{fp}"  # simplified grid notation

    # Player IDs
    u_player_id = u_stats.get("understat_player_id") if u_stats else None
    pid = _player_id(player_name, team_canonical)

    stats = PlayerStats(
        games=PlayerGames(
            minutes=minutes,
            position=position_code,
            rating=None,
            captain=False,
        ),
        goals=PlayerGoals(
            total=goals,
            conceded=goals_conceded,
            assists=assists,
            saves=saves if position_code == "G" else None,
        ),
        shots=PlayerShots(
            total=shots_total,
            on=shots_on,
        ),
        passes=PlayerPasses(
            total=None,
            key=key_passes,
            accuracy=None,
        ),
        tackles=PlayerTackles(
            total=None,
            blocks=None,
            interceptions=None,
        ),
        duels=PlayerDuels(total=None, won=None),
        dribbles=PlayerDribbles(attempts=None, success=None),
        cards=PlayerCards(yellow=yellow, red=red),
    )

    return Player(
        player_id=pid,
        name=player_name,
        photo=_player_photo_url(player_name, team_fpl_id, u_player_id),
        team_id=team_fpl_id,
        team_name=team_canonical,
        team_logo=team_fpl_logo,
        nationality="",
        country_code="xx",
        position_code=position_code,
        grid_position=grid_pos,
        stats=stats,
        fixture_id=fixture_id,
        fixture_result=fixture_result,
    )


# ---------------------------------------------------------------------------
# Fetch and cache player stats for a matchweek
# ---------------------------------------------------------------------------

def fetch_players(matchweek: int) -> dict[int, list[Player]]:
    """
    Fetch player stats for all fixtures in a matchweek.
    Returns {fixture_id: [Player, ...]}
    Caches each fixture to players_{fixture_id}.json.
    """
    fixtures = fetch_fixtures(matchweek)
    data_dir = matchweek_data_dir(matchweek)
    result: dict[int, list[Player]] = {}

    for fixture in fixtures:
        if not fixture.is_complete:
            print(f"  [Skip] {fixture.home_team.name} vs {fixture.away_team.name} not complete yet")
            result[fixture.fixture_id] = []
            continue

        cache_path = data_dir / f"players_{fixture.fixture_id}.json"
        if cache_exists(cache_path):
            print(f"  [Cache] Players already cached for fixture {fixture.fixture_id}")
            result[fixture.fixture_id] = []  # downstream reads directly from file
            continue

        home_canonical = FPL_TO_CANONICAL.get(fixture.home_team.name, fixture.home_team.name)
        away_canonical = FPL_TO_CANONICAL.get(fixture.away_team.name, fixture.away_team.name)
        kickoff = fixture.date

        print(f"  [Fetch] {fixture.home_team.name} vs {fixture.away_team.name} (fixture {fixture.fixture_id})")

        # --- Fetch Understat + ESPN in parallel ---
        u_game_id = _find_understat_game_id(home_canonical, away_canonical, kickoff)
        e_game_id = _find_espn_game_id(home_canonical, away_canonical, kickoff)

        u_players: dict[str, dict] = {}
        e_players: dict[str, dict] = {}

        def _fetch_u():
            if not u_game_id:
                return []
            return _fetch_understat_player_stats(u_game_id)

        def _fetch_e():
            if not e_game_id:
                return []
            return _fetch_espn_lineup(e_game_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fu = pool.submit(_fetch_u)
            fe = pool.submit(_fetch_e)
            try:
                u_raw = fu.result(timeout=60)
                print(f"    [Understat] game_id={u_game_id} → {len(u_raw)} players") if u_game_id else print(f"    [Understat] No match: {home_canonical} vs {away_canonical}")
                for p in u_raw:
                    u_players[_normalize_player_name(p["player_name"])] = p
            except Exception as ex:
                print(f"    [Understat] Error: {ex}")
            try:
                e_raw = fe.result(timeout=60)
                print(f"    [ESPN] game_id={e_game_id} → {len(e_raw)} players") if e_game_id else print(f"    [ESPN] No match: {home_canonical} vs {away_canonical}")
                for p in e_raw:
                    if p.get("formation_place", 0) == 0 and p.get("minutes", 0) == 0:
                        continue
                    e_players[_normalize_player_name(p["player_name"])] = p
            except Exception as ex:
                print(f"    [ESPN] Error: {ex}")

        # --- Merge into Player objects ---
        fixture_result = fixture.result
        all_names: set[str] = set(u_players.keys()) | set(e_players.keys())

        players: list[Player] = []
        for norm_name in sorted(all_names):
            u = u_players.get(norm_name)
            e = e_players.get(norm_name)

            # Determine team
            if e:
                raw_team = e.get("team", "")
                team_canonical = ESPN_TO_CANONICAL.get(raw_team, raw_team)
            elif u:
                raw_team = u.get("team", "")
                team_canonical = UNDERSTAT_TO_CANONICAL.get(raw_team, raw_team)
            else:
                continue

            # Get FPL team ID + logo for this team
            fpl_id, logo = _canonical_to_fpl_id_logo(team_canonical)

            # Original (non-normalized) name: prefer ESPN then Understat
            orig_name = e["player_name"] if e else u["player_name"]

            p = _build_player(
                player_name=orig_name,
                team_canonical=team_canonical,
                team_fpl_id=fpl_id,
                team_fpl_logo=logo,
                fixture_id=fixture.fixture_id,
                fixture_result=fixture_result,
                u_stats=u,
                e_stats=e,
            )

            # Only keep players who played (minutes > 0)
            if p.stats.minutes_played > 0:
                players.append(p)

        # Save in API-Football-compatible format
        af_format = _players_to_api_football_format(players, fixture)
        players = _deduplicate_players(players)
        af_format = _players_to_api_football_format(players, fixture)
        save_json_cache(cache_path, af_format)
        print(f"    [Cache] Saved {len(players)} players for fixture {fixture.fixture_id}")
        result[fixture.fixture_id] = players
        time.sleep(0.5)  # brief pause between fixtures

    return result


def _deduplicate_players(players: list[Player]) -> list[Player]:
    """
    Remove duplicate players caused by name discrepancies between Understat and ESPN.
    Heuristic: if one normalized name is contained in another and both are on the same team,
    keep the one with more complete stats (more non-null fields).
    """
    result: list[Player] = []
    used: set[int] = set()

    def _completeness(p: Player) -> int:
        s = p.stats
        score = 0
        if s.games.minutes: score += 1
        if s.goals.total is not None: score += 1
        if s.goals.assists is not None: score += 1
        if s.goals.saves is not None: score += 2
        if s.passes.key is not None: score += 1
        if s.shots.on is not None: score += 1
        return score

    for i, p in enumerate(players):
        if i in used:
            continue
        p_norm = p.name.lower().replace(".", "").replace("-", " ").strip()
        for j, q in enumerate(players):
            if j <= i or j in used:
                continue
            if p.team_id != q.team_id:
                continue
            q_norm = q.name.lower().replace(".", "").replace("-", " ").strip()
            # Check if one name is contained in the other (same player, different name forms)
            if p_norm in q_norm or q_norm in p_norm:
                # Keep the one with more complete stats
                if _completeness(q) > _completeness(p):
                    used.add(i)
                    break
                else:
                    used.add(j)

        if i not in used:
            result.append(p)

    return result


def _players_to_api_football_format(players: list[Player], fixture: Fixture) -> list[dict]:
    """Convert Player list to API-Football players response format for cache compatibility."""
    # Group by team
    by_team: dict[int, list[Player]] = {}
    for p in players:
        by_team.setdefault(p.team_id, []).append(p)

    result = []
    for team_id, team_players in by_team.items():
        if not team_players:
            continue
        first = team_players[0]
        # Determine team name from fixture
        if team_id == fixture.home_team.id:
            team_name = fixture.home_team.name
            team_logo = fixture.home_team.logo
        elif team_id == fixture.away_team.id:
            team_name = fixture.away_team.name
            team_logo = fixture.away_team.logo
        else:
            team_name = first.team_name
            team_logo = first.team_logo

        team_entry = {
            "team": {"id": team_id, "name": team_name, "logo": team_logo},
            "players": [],
        }
        for p in team_players:
            s = p.stats
            team_entry["players"].append({
                "player": {
                    "id": p.player_id,
                    "name": p.name,
                    "photo": p.photo,
                },
                "statistics": [{
                    "games": {
                        "minutes": s.games.minutes,
                        "position": s.games.position,
                        "rating": s.games.rating,
                        "captain": s.games.captain,
                    },
                    "goals": {
                        "total": s.goals.total,
                        "conceded": s.goals.conceded,
                        "assists": s.goals.assists,
                        "saves": s.goals.saves,
                    },
                    "shots": {"total": s.shots.total, "on": s.shots.on},
                    "passes": {"total": s.passes.total, "key": s.passes.key, "accuracy": s.passes.accuracy},
                    "tackles": {"total": s.tackles.total, "blocks": s.tackles.blocks, "interceptions": s.tackles.interceptions},
                    "duels": {"total": s.duels.total, "won": s.duels.won},
                    "dribbles": {"attempts": s.dribbles.attempts, "success": s.dribbles.success},
                    "cards": {"yellow": s.cards.yellow, "red": s.cards.red},
                    "penalty": {"won": None, "committed": None, "scored": None, "missed": None, "saved": None},
                }],
            })
        result.append(team_entry)

    return result


def _canonical_to_fpl_id_logo(canonical: str) -> tuple[int, str]:
    """Reverse-lookup FPL team ID from canonical name."""
    teams = _load_fpl_teams()
    for fpl_id, info in teams.items():
        if info["canonical"] == canonical:
            return fpl_id, _team_badge_url(fpl_id)
    return 0, ""


# ---------------------------------------------------------------------------
# Fetch and cache lineups for a matchweek
# ---------------------------------------------------------------------------

def fetch_lineups(matchweek: int) -> dict[int, dict]:
    """
    Fetch lineup / formation data for all fixtures in a matchweek.
    Formation is inferred from ESPN formation_place + position data.
    Caches to lineups_{fixture_id}.json.
    """
    fixtures = fetch_fixtures(matchweek)
    data_dir = matchweek_data_dir(matchweek)
    result: dict[int, dict] = {}

    for fixture in fixtures:
        if not fixture.is_complete:
            result[fixture.fixture_id] = {}
            continue

        cache_path = data_dir / f"lineups_{fixture.fixture_id}.json"
        if cache_exists(cache_path):
            print(f"  [Cache] Loading lineups for fixture {fixture.fixture_id}")
            result[fixture.fixture_id] = load_json_cache(cache_path)
            continue

        home_canonical = FPL_TO_CANONICAL.get(fixture.home_team.name, fixture.home_team.name)
        away_canonical = FPL_TO_CANONICAL.get(fixture.away_team.name, fixture.away_team.name)

        e_game_id = _find_espn_game_id(home_canonical, away_canonical, fixture.date)
        if not e_game_id:
            print(f"  [ESPN] No lineup found for fixture {fixture.fixture_id}")
            result[fixture.fixture_id] = {}
            continue

        print(f"  [Lineup] {fixture.home_team.name} vs {fixture.away_team.name} (ESPN id={e_game_id})")
        try:
            espn_players = _fetch_espn_lineup(e_game_id)
        except Exception as ex:
            print(f"  [ESPN] Lineup error: {ex}")
            result[fixture.fixture_id] = {}
            continue

        # Build lineup per team
        lineup: dict[str, dict] = {
            "fixture_id": fixture.fixture_id,
            "home_team": {"name": fixture.home_team.name, "formation": "", "starters": []},
            "away_team": {"name": fixture.away_team.name, "formation": "", "starters": []},
        }

        home_starters = [p for p in espn_players if p["is_home"] and p["formation_place"] > 0]
        away_starters = [p for p in espn_players if not p["is_home"] and p["formation_place"] > 0]

        lineup["home_team"]["formation"] = _infer_formation(home_starters)
        lineup["home_team"]["starters"] = home_starters
        lineup["away_team"]["formation"] = _infer_formation(away_starters)
        lineup["away_team"]["starters"] = away_starters

        # Convert to API-Football lineup format
        af_lineup = _lineup_to_api_football_format(lineup, fixture)
        save_json_cache(cache_path, af_lineup)
        result[fixture.fixture_id] = lineup
        time.sleep(0.5)

    return result


def _lineup_to_api_football_format(lineup: dict, fixture: Fixture) -> list[dict]:
    """Convert lineup dict to API-Football lineups response format."""
    result = []
    for side in ("home_team", "away_team"):
        team_data = lineup.get(side, {})
        starters = team_data.get("starters", [])
        team_name = team_data.get("name", "")
        formation = team_data.get("formation", "4-3-3")

        if side == "home_team":
            team_id = fixture.home_team.id
        else:
            team_id = fixture.away_team.id

        start_xi = []
        for i, p in enumerate(starters, 1):
            espn_pos = p.get("position", "")
            pos_code = ESPN_POS_TO_CODE.get(espn_pos, "M")
            tactical = ESPN_POS_TO_TACTICAL.get(espn_pos, "M")
            fp = p.get("formation_place", i)
            start_xi.append({
                "player": {
                    "id": _player_id(p["player_name"], team_name),
                    "name": p["player_name"],
                    "pos": pos_code,
                    "grid": f"1:{fp}",
                }
            })

        result.append({
            "team": {"id": team_id, "name": team_name},
            "formation": formation,
            "startXI": start_xi,
            "substitutes": [],
        })

    return result


def _infer_formation(starters: list[dict]) -> str:
    """
    Infer formation string (e.g. '4-3-3') from ESPN starters' positions.
    Counts defenders, midfielders, forwards.
    """
    n_def = sum(1 for p in starters if ESPN_POS_TO_CODE.get(p.get("position", ""), "") == "D")
    n_mid = sum(1 for p in starters if ESPN_POS_TO_CODE.get(p.get("position", ""), "") == "M")
    n_fwd = sum(1 for p in starters if ESPN_POS_TO_CODE.get(p.get("position", ""), "") == "F")

    if n_def + n_mid + n_fwd == 10:  # excluding GK
        return f"{n_def}-{n_mid}-{n_fwd}"
    return "4-3-3"  # fallback


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_check_budget():
    print("FPL API + soccerdata (Understat + ESPN): no daily rate limit.")
    print("FPL API: public, no key needed.")
    print("Understat: web scraping with built-in rate limiting.")
    print("ESPN: web scraping with built-in rate limiting.")
    print("soccerdata caches to ~/soccerdata/data/ automatically.")
    print("Project cache: data/2025-26/matchweek-{N}/")


def cmd_check_status(matchweek: int):
    _load_fpl_teams()
    raw_fixtures = _fetch_fpl_fixtures(matchweek)
    total = len(raw_fixtures)
    completed = sum(1 for f in raw_fixtures if f.get("finished", False))
    print(f"\nMatchweek {matchweek} status: {completed}/{total} fixtures complete")
    print()
    for f in raw_fixtures:
        home = _fpl_team_name(f["team_h"])
        away = _fpl_team_name(f["team_a"])
        if f.get("finished"):
            score = f"{f['team_h_score']} - {f['team_a_score']}"
            print(f"  ✅ {home:25s} {score:7s} {away}")
        elif f.get("started"):
            print(f"  🔴 {home:25s} LIVE    {away}")
        else:
            ko = f.get("kickoff_time", "TBD")[:16].replace("T", " ")
            print(f"  ⏳ {home:25s} {ko:7s} {away}")


def cmd_fetch_round(matchweek: int):
    fixtures = fetch_fixtures(matchweek)
    print(f"\nMatchweek {matchweek}: {len(fixtures)} fixtures fetched.")
    for f in fixtures:
        status = "✅" if f.is_complete else "⏳"
        print(f"  {status} [{f.fixture_id}] {f.home_team.name} {f.score_str} {f.away_team.name}")


def cmd_fetch_players(matchweek: int):
    players_by_fixture = fetch_players(matchweek)
    total = sum(len(v) for v in players_by_fixture.values())
    print(f"\nMatchweek {matchweek}: player stats fetched.")
    for fid, players in players_by_fixture.items():
        print(f"  Fixture {fid}: {len(players)} players")
    print(f"  Total: {total} players")


def cmd_fetch_lineups(matchweek: int):
    lineups = fetch_lineups(matchweek)
    print(f"\nMatchweek {matchweek}: lineups fetched.")
    for fid, lineup in lineups.items():
        if lineup:
            h_form = lineup.get("home_team", {}).get("formation", "?")
            a_form = lineup.get("away_team", {}).get("formation", "?")
            h_name = lineup.get("home_team", {}).get("name", "?")
            a_name = lineup.get("away_team", {}).get("name", "?")
            print(f"  [{fid}] {h_name} ({h_form}) vs {a_name} ({a_form})")
        else:
            print(f"  [{fid}] No lineup data")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "check-budget":
        cmd_check_budget()
    elif command == "check-status":
        matchweek = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        cmd_check_status(matchweek)
    elif command == "fetch-round":
        matchweek = int(sys.argv[2])
        cmd_fetch_round(matchweek)
    elif command == "fetch-players":
        matchweek = int(sys.argv[2])
        cmd_fetch_players(matchweek)
    elif command == "fetch-lineups":
        matchweek = int(sys.argv[2])
        cmd_fetch_lineups(matchweek)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
