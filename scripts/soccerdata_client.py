"""
soccerdata_client.py — Multi-source data client for EPL TOTW Builder (2025-26 season).

Data sources:
- FPL API (fantasy.premierleague.com): Matchweek fixtures, scores, team IDs. No key needed.
- SofaScore API (api.sofascore.com): All 66 player stats per match — goals, assists, key_passes,
  minutes, shots, tackles, interceptions, clearances, aerial duels, pass accuracy, rating, xG/xA.
  Accessed via tls_requests (installed as a soccerdata dependency). Game IDs resolved via
  soccerdata.Sofascore schedule. Single call per match replaces both Understat + ESPN.

No API key required. soccerdata handles schedule caching in ~/soccerdata/data/.
This script adds a second cache layer in data/2025-26/matchweek-{N}/ (same layout as api_football.py).

CLI:
  python scripts/soccerdata_client.py check-budget
  python scripts/soccerdata_client.py check-status 28
  python scripts/soccerdata_client.py fetch-round 28
  python scripts/soccerdata_client.py fetch-players 28
  python scripts/soccerdata_client.py fetch-lineups 28
  python scripts/soccerdata_client.py fetch-players-subset 28 id1 id2 id3 ...
  python scripts/soccerdata_client.py fetch-lineups-subset 28 id1 id2 id3 ...
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
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

# SofaScore uses "XXYY" format for season: 2526 = 2025-26
SOFASCORE_SEASON = "2526"

# SofaScore API base URL
SOFASCORE_API_BASE = "https://api.sofascore.com/api/v1"

# FPL API base (no key needed, public)
FPL_BASE = "https://fantasy.premierleague.com/api"

# ---------------------------------------------------------------------------
# Team name normalization: FPL / SofaScore → canonical name
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

# SofaScore team names → canonical
SOFASCORE_TO_CANONICAL: dict[str, str] = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Burnley": "Burnley",
    "Bournemouth": "Bournemouth",
    "AFC Bournemouth": "Bournemouth",
    "Brentford": "Brentford",
    "Brighton & Hove Albion": "Brighton",
    "Brighton": "Brighton",
    "Chelsea": "Chelsea",
    "Crystal Palace": "Crystal Palace",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Leeds": "Leeds",
    "Leeds United": "Leeds",
    "Liverpool": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottm Forest",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur": "Spurs",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Wolverhampton": "Wolves",
}

# SofaScore position name → API-Football position code (G/D/M/F)
SOFASCORE_POS_TO_CODE: dict[str, str] = {
    "Goalkeeper": "G",
    "Defender": "D",
    "Midfielder": "M",
    "Forward": "F",
}


def _normalize_team(name: str, mapping: dict[str, str]) -> str:
    """Map team name to canonical form. Falls back to the original name."""
    return mapping.get(name, name)


# ---------------------------------------------------------------------------
# SofaScore schedule cache (game_id lookup)
# ---------------------------------------------------------------------------

_sofascore_schedule_cache: Optional[list[dict]] = None


def _get_sofascore_schedule() -> list[dict]:
    """Load SofaScore 2025-26 schedule, cached to data/sofascore_schedule_2526.json."""
    global _sofascore_schedule_cache
    if _sofascore_schedule_cache:
        return _sofascore_schedule_cache

    cache_path = Path(__file__).parent.parent / "data" / "sofascore_schedule_2526.json"
    cached = load_json_cache(cache_path)
    if cached:
        _sofascore_schedule_cache = cached
        return cached

    print("  [SofaScore] Fetching 2025-26 schedule via soccerdata...")
    import soccerdata as sd
    ss = sd.Sofascore(leagues="ENG-Premier League", seasons=SOFASCORE_SEASON)
    sched = ss.read_schedule().reset_index()
    records = sched.to_dict(orient="records")
    # Convert any non-serializable types
    clean = []
    for r in records:
        clean.append({k: (str(v) if hasattr(v, "isoformat") else v) for k, v in r.items()})
    save_json_cache(cache_path, clean)
    _sofascore_schedule_cache = clean
    print(f"  [SofaScore] Schedule loaded: {len(clean)} matches")
    return clean


def _find_sofascore_game_id(home_canonical: str, away_canonical: str, kickoff: str) -> Optional[int]:
    """Find SofaScore event/game_id by matching canonical team names + date."""
    schedule = _get_sofascore_schedule()
    date_prefix = str(kickoff)[:10]

    for row in schedule:
        ss_home = SOFASCORE_TO_CANONICAL.get(str(row.get("home_team", "")), str(row.get("home_team", "")))
        ss_away = SOFASCORE_TO_CANONICAL.get(str(row.get("away_team", "")), str(row.get("away_team", "")))
        ss_date = str(row.get("date", ""))[:10]
        if ss_home == home_canonical and ss_away == away_canonical and ss_date == date_prefix:
            return int(row["game_id"])
    return None


# ---------------------------------------------------------------------------
# SofaScore direct API (tls_requests bypasses 403 from standard urllib)
# ---------------------------------------------------------------------------

def _sofascore_api_get(path: str) -> dict:
    """GET a SofaScore API endpoint using tls_requests (required to avoid 403)."""
    import tls_requests
    session = tls_requests.Client()
    url = f"{SOFASCORE_API_BASE}{path}"
    resp = session.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.sofascore.com/",
    })
    resp.raise_for_status()
    return resp.json()


def _calc_sofascore_minutes(subbed_in: Optional[int], subbed_out: Optional[int],
                             is_starter: bool) -> int:
    """Compute minutes played from SofaScore substitution data."""
    start = subbed_in if subbed_in is not None else (0 if is_starter else None)
    end = subbed_out if subbed_out is not None else 90
    if start is None:
        return 0
    return max(0, end - start)


# SofaScore alpha2 → API-Football country code (British nations use compound codes)
_SS_COUNTRY_MAP: dict[str, str] = {
    "EN": "gb-eng",
    "SC": "gb-sct",
    "WL": "gb-wls",
    "NI": "gb-nir",
    "GB": "gb-eng",   # Generic GB fallback
}

# SofaScore position code (G/D/M/F) → full name (for SOFASCORE_POS_TO_CODE lookup)
_SS_POS_TO_NAME: dict[str, str] = {
    "G": "Goalkeeper",
    "D": "Defender",
    "M": "Midfielder",
    "F": "Forward",
}


def _parse_sofascore_team(team_data: dict, goals_conceded: Optional[int]) -> tuple[str, list[dict]]:
    """Parse one team's lineups response into (formation_string, [player_stat_dicts])."""
    formation = team_data.get("formation", "")
    players_raw = team_data.get("players", [])
    result = []
    for entry in players_raw:
        p = entry.get("player", {})
        stats = entry.get("statistics", {})

        # position is a single-letter string ("G", "D", "M", "F") at entry level
        pos_code_raw = entry.get("position") or p.get("position") or "M"
        pos_name = _SS_POS_TO_NAME.get(str(pos_code_raw), "Midfielder")

        is_starter = not entry.get("substitute", True)

        # Use minutesPlayed from statistics (most reliable)
        minutes = stats.get("minutesPlayed") or 0

        # Country code: player.country.alpha2 with British nation mapping
        country_info = p.get("country") or {}
        raw_alpha2 = str(country_info.get("alpha2", "")).upper()
        country_code = _SS_COUNTRY_MAP.get(raw_alpha2, raw_alpha2.lower()) if raw_alpha2 else "xx"

        total_pass = stats.get("totalPass", 0) or 0
        accurate_pass = stats.get("accuratePass", 0) or 0
        pass_acc = str(round(accurate_pass / total_pass * 100, 1)) if total_pass > 0 else None

        duel_won = stats.get("duelWon", 0) or 0
        duel_lost = stats.get("duelLost", 0) or 0

        result.append({
            "player_id":         p.get("id"),
            "player_name":       p.get("name", ""),
            "position_name":     pos_name,
            "position_code":     str(pos_code_raw),
            "country_code":      country_code,
            "minutes":           minutes,
            "is_starter":        is_starter,
            "goals":             stats.get("goals", 0) or 0,
            "assists":           stats.get("goalAssist", 0) or 0,
            "key_passes":        stats.get("keyPass", 0) or 0,
            "shots_on_target":   stats.get("onTargetScoringAttempt", 0) or 0,
            "shots_total":       (stats.get("totalShots", 0) or 0),
            "total_pass":        total_pass,
            "pass_accuracy":     pass_acc,
            "accurate_crosses":  stats.get("accurateCross", 0) or 0,
            "tackles_won":       stats.get("wonTackle", 0) or 0,
            "interceptions":     stats.get("interceptionWon", 0) or 0,
            "clearances":        stats.get("totalClearance", 0) or 0,
            "blocks":            stats.get("outfielderBlock", 0) or 0,
            "duel_won":          duel_won,
            "duel_lost":         duel_lost,
            "duel_total":        duel_won + duel_lost,
            "aerial_won":        stats.get("aerialWon", 0) or 0,
            "aerial_lost":       stats.get("aerialLost", 0) or 0,
            "dribbles_success":  stats.get("wonContest", 0) or 0,
            "dribbles_attempts": stats.get("totalContest", 0) or 0,
            "saves":             stats.get("saves", 0) or 0,
            "goals_conceded":    goals_conceded if str(pos_code_raw) == "G" else None,
            "yellow_cards":      1 if stats.get("yellowCard") else 0,
            "red_cards":         1 if stats.get("directRedCard") or stats.get("redCard") else 0,
            "rating":            stats.get("rating"),   # float e.g. 7.4
            "xg":                stats.get("expectedGoals"),
            "xa":                stats.get("expectedAssists"),
        })
    return formation, result


# ---------------------------------------------------------------------------
# FPL team registry (loaded once from bootstrap-static)
# ---------------------------------------------------------------------------

_FPL_TEAMS: dict[int, dict] = {}   # id → {name, canonical, short_name, code}

# FPL player photo lookup: (normalized_full_name, fpl_team_id) → photo_url
_FPL_PLAYER_PHOTOS: dict[tuple[str, int], str] = {}
_FPL_PLAYER_PHOTOS_LOADED = False

# FootballTransfers.com player info cache: player_name_lower → {photo, country_code}
_FT_PLAYER_INFO: dict[str, dict] = {}
_FT_CACHE_PATH: Path | None = None


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
        photo_url = f"https://resources.premierleague.com/premierleague25/photos/players/110x140/{code}.png"
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


def _ft_player_info(player_name: str) -> dict:
    """Look up player info from FootballTransfers.com search API.

    Returns dict with keys: photo (URL string), country_code (ISO 2-letter lowercase).
    Results cached in data/ft_player_photos.json. Returns empty dict on failure.

    The search flag URL pattern: .../flags/w40/{country_code}.png
    """
    global _FT_PLAYER_INFO, _FT_CACHE_PATH

    if _FT_CACHE_PATH is None:
        _FT_CACHE_PATH = Path(__file__).parent.parent / "data" / "ft_player_photos.json"
        cached = load_json_cache(_FT_CACHE_PATH)
        if cached:
            _FT_PLAYER_INFO = cached

    name_lower = player_name.strip().lower()
    if name_lower in _FT_PLAYER_INFO:
        return _FT_PLAYER_INFO[name_lower]

    try:
        url = "https://www.footballtransfers.com/en/search/actions/search"
        post_data = urllib.parse.urlencode({"search_value": player_name}).encode()
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        hits = result.get("hits", [])
        if not hits:
            _FT_PLAYER_INFO[name_lower] = {}
            save_json_cache(_FT_CACHE_PATH, _FT_PLAYER_INFO)
            return {}

        # First hit is the best match
        doc = hits[0]["document"]

        # Extract photo URL from proxy wrapper
        raw_img = doc.get("image", "")
        parsed = urllib.parse.urlparse(raw_img)
        qs = urllib.parse.parse_qs(parsed.query)
        photo_url = qs.get("url", [raw_img])[0]

        # Extract country code from flag URL: .../flags/w40/{code}.png
        # FT uses "uk" for British players; normalize to API-Football codes
        _FT_COUNTRY_MAP = {
            "uk": "gb-eng",   # FT uses uk for all British — default to England flag
            "gb": "gb-eng",
        }
        country_code = "xx"
        flag_raw = doc.get("flag", "")
        flag_parsed = urllib.parse.urlparse(flag_raw)
        flag_qs = urllib.parse.parse_qs(flag_parsed.query)
        flag_url = flag_qs.get("url", [flag_raw])[0]
        # URL ends with e.g. "/flags/w40/fr.png" or "/flags/w40/gb-eng.png"
        if flag_url:
            flag_base = flag_url.rsplit("/", 1)[-1]  # "fr.png"
            raw_code = flag_base.rsplit(".", 1)[0].lower()  # "fr"
            country_code = _FT_COUNTRY_MAP.get(raw_code, raw_code)

        info = {"photo": photo_url, "country_code": country_code}
        _FT_PLAYER_INFO[name_lower] = info
        save_json_cache(_FT_CACHE_PATH, _FT_PLAYER_INFO)
        return info

    except Exception:
        _FT_PLAYER_INFO[name_lower] = {}
        if _FT_CACHE_PATH:
            save_json_cache(_FT_CACHE_PATH, _FT_PLAYER_INFO)
        return {}


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


def _player_photo_url(player_name: str, fpl_team_id: int, understat_player_id: Optional[int],
                      team_canonical: str = "") -> str:
    """Best-effort player photo URL.
    Priority: FootballTransfers.com (primary) → FPL CDN → Understat.
    """
    info = _ft_player_info(player_name)
    if info.get("photo"):
        return info["photo"]
    fpl_photo = _fpl_player_photo(player_name, fpl_team_id)
    if fpl_photo:
        return fpl_photo
    if understat_player_id:
        return f"https://understat.com/images/player/{understat_player_id}.jpg"
    return ""


def _player_country_code(player_name: str) -> str:
    """Return ISO country code (lowercase) from FootballTransfers lookup. Returns 'xx' if unknown."""
    info = _ft_player_info(player_name)
    return info.get("country_code", "xx") or "xx"


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
# Build Player model from SofaScore parsed dict
# ---------------------------------------------------------------------------

def _build_sofascore_player(
    ss: dict,
    team_canonical: str,
    team_fpl_id: int,
    team_fpl_logo: str,
    fixture_id: int,
    fixture_result: Optional[str],
) -> Player:
    """Build a Player Pydantic model from a SofaScore player stat dict."""
    pos_code = SOFASCORE_POS_TO_CODE.get(ss["position_name"], "M")
    rating_raw = ss.get("rating")
    rating_str = str(round(float(rating_raw), 1)) if rating_raw else None

    stats = PlayerStats(
        games=PlayerGames(
            minutes=ss["minutes"],
            position=pos_code,
            rating=rating_str,
            captain=False,
        ),
        goals=PlayerGoals(
            total=ss["goals"],
            conceded=ss.get("goals_conceded"),
            assists=ss["assists"],
            saves=ss["saves"] if pos_code == "G" else None,
        ),
        shots=PlayerShots(
            total=ss["shots_total"],
            on=ss["shots_on_target"],
        ),
        passes=PlayerPasses(
            total=ss["total_pass"],
            key=ss["key_passes"],
            accuracy=ss["pass_accuracy"],
            accurate_crosses=ss["accurate_crosses"],
        ),
        tackles=PlayerTackles(
            total=ss["tackles_won"],
            blocks=ss["blocks"],
            interceptions=ss["interceptions"],
            clearances=ss["clearances"],
        ),
        duels=PlayerDuels(
            total=ss["duel_total"],
            won=ss["duel_won"],
            aerial_won=ss["aerial_won"],
            aerial_lost=ss["aerial_lost"],
        ),
        dribbles=PlayerDribbles(
            attempts=ss["dribbles_attempts"],
            success=ss["dribbles_success"],
        ),
        cards=PlayerCards(
            yellow=ss["yellow_cards"],
            red=ss["red_cards"],
        ),
    )

    # Use SofaScore country code directly; fall back to FootballTransfers if missing
    country_code = ss.get("country_code") or ""
    if not country_code or country_code == "xx":
        country_code = _player_country_code(ss["player_name"])

    return Player(
        player_id=_player_id(ss["player_name"], team_canonical),
        name=ss["player_name"],
        photo=_player_photo_url(ss["player_name"], team_fpl_id, None, team_canonical),
        team_id=team_fpl_id,
        team_name=team_canonical,
        team_logo=team_fpl_logo,
        nationality="",
        country_code=country_code,
        position_code=pos_code,
        grid_position=ss.get("position_code") or None,
        stats=stats,
        fixture_id=fixture_id,
        fixture_result=fixture_result,
    )


def _sofascore_lineup_to_cache_format(
    fixture: Fixture,
    home_form: str,
    away_form: str,
    home_players: list[dict],
    away_players: list[dict],
) -> list[dict]:
    """Convert SofaScore lineup data to API-Football lineups_{id}.json format."""
    result = []
    for side, form, players, team in [
        ("home", home_form, home_players, fixture.home_team),
        ("away", away_form, away_players, fixture.away_team),
    ]:
        starters = [p for p in players if p.get("is_starter")]
        start_xi = []
        for i, p in enumerate(starters, 1):
            pos_code = SOFASCORE_POS_TO_CODE.get(p["position_name"], "M")
            start_xi.append({
                "player": {
                    "id": _player_id(p["player_name"], team.name),
                    "name": p["player_name"],
                    "pos": pos_code,
                    "grid": f"1:{i}",
                }
            })
        result.append({
            "team": {"id": team.id, "name": team.name},
            "formation": form,
            "startXI": start_xi,
            "substitutes": [],
        })
    return result


# ---------------------------------------------------------------------------
# Fetch and cache player stats for a matchweek
# ---------------------------------------------------------------------------

def fetch_players(matchweek: int, only_fixture_ids: Optional[list[int]] = None) -> dict[int, list[Player]]:
    """
    Fetch player stats for all (or a subset of) fixtures in a matchweek.
    Returns {fixture_id: [Player, ...]}
    Caches each fixture to players_{fixture_id}.json.
    Pass only_fixture_ids to restrict fetching to those IDs (used by parallel agents).
    """
    fixtures = fetch_fixtures(matchweek)
    if only_fixture_ids is not None:
        id_set = set(only_fixture_ids)
        fixtures = [f for f in fixtures if f.fixture_id in id_set]
    data_dir = matchweek_data_dir(matchweek)
    result: dict[int, list[Player]] = {}

    for fixture in fixtures:
        if not fixture.is_complete:
            print(f"  [Skip] {fixture.home_team.name} vs {fixture.away_team.name} not complete yet")
            result[fixture.fixture_id] = []
            continue

        players_cache = data_dir / f"players_{fixture.fixture_id}.json"
        lineups_cache = data_dir / f"lineups_{fixture.fixture_id}.json"

        if cache_exists(players_cache):
            print(f"  [Cache] Players already cached for fixture {fixture.fixture_id}")
            result[fixture.fixture_id] = []  # downstream reads directly from file
            continue

        home_canonical = FPL_TO_CANONICAL.get(fixture.home_team.name, fixture.home_team.name)
        away_canonical = FPL_TO_CANONICAL.get(fixture.away_team.name, fixture.away_team.name)

        print(f"  [Fetch] {fixture.home_team.name} vs {fixture.away_team.name} (fixture {fixture.fixture_id})")

        ss_game_id = _find_sofascore_game_id(home_canonical, away_canonical, fixture.date)
        if not ss_game_id:
            print(f"    [SofaScore] No game_id found for {home_canonical} vs {away_canonical} on {fixture.date[:10]}")
            result[fixture.fixture_id] = []
            continue

        try:
            data = _sofascore_api_get(f"/event/{ss_game_id}/lineups")
        except Exception as ex:
            print(f"    [SofaScore] API error for game_id={ss_game_id}: {ex}")
            result[fixture.fixture_id] = []
            continue

        # Scores for goals_conceded calculation
        home_score = fixture.score.home if fixture.score.home is not None else 0
        away_score = fixture.score.away if fixture.score.away is not None else 0

        home_form, home_ss = _parse_sofascore_team(data.get("home", {}), away_score)
        away_form, away_ss = _parse_sofascore_team(data.get("away", {}), home_score)

        print(f"    [SofaScore] game_id={ss_game_id} → {len(home_ss)} home + {len(away_ss)} away players | {home_form} vs {away_form}")

        # Build Player objects (both teams combined)
        fixture_result = fixture.result
        home_fpl_id, home_logo = _canonical_to_fpl_id_logo(home_canonical)
        away_fpl_id, away_logo = _canonical_to_fpl_id_logo(away_canonical)

        players: list[Player] = []
        for ss_entry, team_canonical, fpl_id, logo in [
            *[(p, home_canonical, home_fpl_id, home_logo) for p in home_ss],
            *[(p, away_canonical, away_fpl_id, away_logo) for p in away_ss],
        ]:
            if ss_entry["minutes"] > 0:
                players.append(_build_sofascore_player(
                    ss=ss_entry,
                    team_canonical=team_canonical,
                    team_fpl_id=fpl_id,
                    team_fpl_logo=logo,
                    fixture_id=fixture.fixture_id,
                    fixture_result=fixture_result,
                ))

        # Save players cache
        af_format = _players_to_api_football_format(players, fixture)
        save_json_cache(players_cache, af_format)
        print(f"    [Cache] Saved {len(players)} players for fixture {fixture.fixture_id}")

        # Save lineups cache (from same SofaScore response — no extra API call)
        if not cache_exists(lineups_cache):
            lineup_data = _sofascore_lineup_to_cache_format(
                fixture, home_form, away_form, home_ss, away_ss
            )
            save_json_cache(lineups_cache, lineup_data)
            print(f"    [Cache] Saved lineups for fixture {fixture.fixture_id} ({home_form} vs {away_form})")

        result[fixture.fixture_id] = players
        time.sleep(1.0)  # polite rate limiting for SofaScore

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
                    "nationality": p.nationality,
                    "country_code": p.country_code,
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
                    "passes": {
                        "total": s.passes.total,
                        "key": s.passes.key,
                        "accuracy": s.passes.accuracy,
                        "accurate_crosses": s.passes.accurate_crosses,
                    },
                    "tackles": {
                        "total": s.tackles.total,
                        "blocks": s.tackles.blocks,
                        "interceptions": s.tackles.interceptions,
                        "clearances": s.tackles.clearances,
                    },
                    "duels": {
                        "total": s.duels.total,
                        "won": s.duels.won,
                        "aerial_won": s.duels.aerial_won,
                        "aerial_lost": s.duels.aerial_lost,
                    },
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

def fetch_lineups(matchweek: int, only_fixture_ids: Optional[list[int]] = None) -> dict[int, dict]:
    """
    Fetch lineup / formation data for all (or a subset of) fixtures in a matchweek.
    With SofaScore, lineups are written by fetch_players in the same API call.
    If lineups_{id}.json is missing, delegates to fetch_players for that fixture.
    Caches to lineups_{fixture_id}.json (API-Football format).
    Pass only_fixture_ids to restrict fetching to those IDs (used by parallel agents).
    """
    fixtures = fetch_fixtures(matchweek)
    if only_fixture_ids is not None:
        id_set = set(only_fixture_ids)
        fixtures = [f for f in fixtures if f.fixture_id in id_set]
    data_dir = matchweek_data_dir(matchweek)
    result: dict[int, dict] = {}

    missing_fixture_ids: list[int] = []
    for fixture in fixtures:
        if not fixture.is_complete:
            result[fixture.fixture_id] = {}
            continue

        cache_path = data_dir / f"lineups_{fixture.fixture_id}.json"
        if cache_exists(cache_path):
            print(f"  [Cache] Loading lineups for fixture {fixture.fixture_id}")
            result[fixture.fixture_id] = load_json_cache(cache_path)
        else:
            missing_fixture_ids.append(fixture.fixture_id)

    if missing_fixture_ids:
        print(f"  [Lineups] {len(missing_fixture_ids)} fixtures missing lineups — fetching via SofaScore...")
        fetch_players(matchweek, only_fixture_ids=missing_fixture_ids)
        # Now read from cache
        for fid in missing_fixture_ids:
            cache_path = data_dir / f"lineups_{fid}.json"
            if cache_exists(cache_path):
                result[fid] = load_json_cache(cache_path)
            else:
                result[fid] = {}

    return result


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_check_budget():
    print("FPL API + SofaScore: no daily rate limit.")
    print("FPL API: public, no key needed.")
    print("SofaScore: direct API via tls_requests (1 call per fixture, ~1s delay).")
    print("soccerdata.Sofascore: schedule only, cached to data/sofascore_schedule_2526.json.")
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


def cmd_fetch_players_subset(matchweek: int, fixture_ids: list[int]):
    """Fetch player stats for a specific subset of fixture IDs (used by parallel agents)."""
    print(f"\nAgent fetching player stats for fixtures: {fixture_ids}")
    result = fetch_players(matchweek, only_fixture_ids=fixture_ids)
    total = sum(len(v) for v in result.values())
    print(f"\nSubset complete — fixtures: {fixture_ids}, total players cached: {total}")


def cmd_fetch_lineups_subset(matchweek: int, fixture_ids: list[int]):
    """Fetch lineup/formation data for a specific subset of fixture IDs (used by parallel agents)."""
    print(f"\nAgent fetching lineups for fixtures: {fixture_ids}")
    fetch_lineups(matchweek, only_fixture_ids=fixture_ids)
    print(f"\nLineup subset complete for fixtures: {fixture_ids}")


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
    elif command == "fetch-players-subset":
        matchweek = int(sys.argv[2])
        fixture_ids = [int(x) for x in sys.argv[3:]]
        cmd_fetch_players_subset(matchweek, fixture_ids)
    elif command == "fetch-lineups-subset":
        matchweek = int(sys.argv[2])
        fixture_ids = [int(x) for x in sys.argv[3:]]
        cmd_fetch_lineups_subset(matchweek, fixture_ids)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
