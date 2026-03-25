"""
API-Football v3 client for the EPL TOTW Builder.

All API calls go through this module. It enforces:
- Rate limiting: max 100 requests/day (tracked in data/.api_usage.json)
- Caching: responses saved to data/2025-26/matchweek-{N}/ before returning

CLI usage:
  python scripts/api_football.py get-current-round
  python scripts/api_football.py check-status 30
  python scripts/api_football.py check-budget
  python scripts/api_football.py fetch-round 30
  python scripts/api_football.py fetch-players 1035049
  python scripts/api_football.py fetch-lineups 1035049
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

# Allow running from project root or scripts/ directory
sys.path.insert(0, str(Path(__file__).parent))

# Load secrets from .claude/settings.local.json if not already in env
_settings_local = Path(__file__).parent.parent / ".claude" / "settings.local.json"
if _settings_local.exists():
    try:
        import json as _json
        _local = _json.loads(_settings_local.read_text())
        for _k, _v in _local.get("env", {}).items():
            if _k not in os.environ and _v:
                os.environ[_k] = _v
    except Exception:
        pass

from utils import (
    cache_exists,
    load_json_cache,
    save_json_cache,
    matchweek_data_dir,
    rate_limiter,
    round_string,
    matchweek_from_round,
    get_country_code,
    team_badge_url,
    player_photo_url,
)
from data_models import (
    Fixture, TeamInfo, Score, FixtureStatus,
    Player, PlayerStats, PlayerGames, PlayerGoals, PlayerShots,
    PlayerPasses, PlayerTackles, PlayerDuels, PlayerDribbles,
    PlayerCards, PlayerPenalty,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io")
API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
LEAGUE_ID = int(os.environ.get("PL_LEAGUE_ID", "39"))
SEASON = int(os.environ.get("PL_SEASON", "2024"))


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def _headers() -> dict:
    if not API_KEY:
        raise EnvironmentError(
            "API_FOOTBALL_KEY is not set. "
            "Add it to .claude/settings.local.json under env."
        )
    return {"x-apisports-key": API_KEY}


_LAST_REQUEST_TIME: float = 0.0
_MIN_REQUEST_INTERVAL: float = 7.0  # Free plan: 10 req/min → 6s min; use 7s to be safe


def _get(endpoint: str, params: dict, retry: int = 3) -> dict:
    """
    Make a GET request to the API-Football endpoint.
    - Enforces 7-second minimum gap between requests (10 req/min free limit).
    - Retries up to 3 times on rate-limit errors (with 65s backoff).
    - Raises RuntimeError if daily limit exceeded.
    """
    global _LAST_REQUEST_TIME

    if not rate_limiter.can_make_request:
        raise RuntimeError(
            f"Daily API rate limit reached ({rate_limiter.DAILY_LIMIT} requests). "
            f"Use cached data or wait until tomorrow."
        )

    # Per-minute throttle: wait until 7s have passed since the last request
    elapsed = time.time() - _LAST_REQUEST_TIME
    if elapsed < _MIN_REQUEST_INTERVAL:
        wait = _MIN_REQUEST_INTERVAL - elapsed
        print(f"  [Rate] Waiting {wait:.1f}s (per-minute limit)...")
        time.sleep(wait)

    url = f"{BASE_URL}/{endpoint}"
    print(f"  [API] GET /{endpoint} {params}")

    for attempt in range(retry):
        _LAST_REQUEST_TIME = time.time()
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        errors = data.get("errors", {})

        if not errors:
            rate_limiter.record_request()
            return data

        # Per-minute rate limit: back off and retry
        if "rateLimit" in errors:
            if attempt < retry - 1:
                backoff = 65
                print(f"  [Rate] Per-minute limit hit. Backing off {backoff}s (attempt {attempt+1}/{retry})...")
                time.sleep(backoff)
                continue
            raise RuntimeError(f"Per-minute rate limit exceeded after {retry} retries.")

        raise RuntimeError(f"API-Football error: {errors}")

    raise RuntimeError("Max retries exceeded.")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def get_current_round() -> str:
    """
    Return the current active round string, e.g. 'Regular Season - 31'.
    Uses cache from today if available.
    """
    from utils import DATA_DIR
    cache_path = DATA_DIR / "current_round.json"

    # Cache for 1 hour (check mtime)
    if cache_path.exists():
        import time as _time
        age = _time.time() - cache_path.stat().st_mtime
        if age < 3600:
            cached = load_json_cache(cache_path)
            if cached and cached.get("round"):
                return cached["round"]

    data = _get("fixtures/rounds", {
        "league": LEAGUE_ID,
        "season": SEASON,
        "current": "true",
    })

    rounds = data.get("response", [])
    if not rounds:
        raise ValueError("No current round returned from API.")

    current = rounds[0]
    save_json_cache(cache_path, {"round": current})
    return current


def fetch_fixtures(matchweek: int) -> list[Fixture]:
    """
    Fetch all fixtures for a given matchweek.
    Caches to data/2025-26/matchweek-{N}/fixtures.json.
    """
    data_dir = matchweek_data_dir(matchweek)
    cache_path = data_dir / "fixtures.json"

    raw = load_json_cache(cache_path)
    if raw is None:
        data = _get("fixtures", {
            "league": LEAGUE_ID,
            "season": SEASON,
            "round": round_string(matchweek),
        })
        raw = data.get("response", [])
        save_json_cache(cache_path, raw)
        print(f"  [Cache] Saved fixtures for matchweek {matchweek} ({len(raw)} fixtures)")
    else:
        print(f"  [Cache] Loaded fixtures for matchweek {matchweek} from cache")

    return [_parse_fixture(f) for f in raw]


def _parse_fixture(raw: dict) -> Fixture:
    fix = raw["fixture"]
    teams = raw["teams"]
    goals = raw["goals"]
    score = raw.get("score", {})

    # Prefer fulltime score
    ft = score.get("fulltime", {})
    home_score = ft.get("home") if ft else goals.get("home")
    away_score = ft.get("away") if ft else goals.get("away")

    return Fixture(
        fixture_id=fix["id"],
        date=fix["date"],
        round=raw["league"]["round"],
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
        score=Score(home=home_score, away=away_score),
        status=FixtureStatus(
            short=fix["status"]["short"],
            long=fix["status"]["long"],
            elapsed=fix["status"].get("elapsed"),
        ),
    )


# ---------------------------------------------------------------------------
# Player stats
# ---------------------------------------------------------------------------

def fetch_fixture_players(fixture_id: int, matchweek: int) -> list[Player]:
    """
    Fetch all player stats for a fixture.
    Caches to data/2025-26/matchweek-{N}/players_{fixture_id}.json.
    """
    data_dir = matchweek_data_dir(matchweek)
    cache_path = data_dir / f"players_{fixture_id}.json"

    raw = load_json_cache(cache_path)
    if raw is None:
        data = _get("fixtures/players", {"fixture": fixture_id})
        raw = data.get("response", [])
        save_json_cache(cache_path, raw)
        print(f"  [Cache] Saved player stats for fixture {fixture_id}")
    else:
        print(f"  [Cache] Loaded player stats for fixture {fixture_id} from cache")

    players = []
    for team_data in raw:
        team = team_data["team"]
        for p in team_data.get("players", []):
            player = _parse_player(p, team, fixture_id)
            if player:
                players.append(player)

    return players


def _parse_player(raw: dict, team: dict, fixture_id: int) -> Player | None:
    info = raw.get("player", {})
    stats_list = raw.get("statistics", [{}])
    stats_raw = stats_list[0] if stats_list else {}

    player_id = info.get("id")
    name = info.get("name", "Unknown")
    if not player_id:
        return None

    nationality = info.get("nationality") or ""
    country_code = get_country_code(nationality)

    games_raw = stats_raw.get("games", {})
    stats = PlayerStats(
        games=PlayerGames(
            minutes=games_raw.get("minutes"),
            position=games_raw.get("position"),
            rating=games_raw.get("rating"),
            captain=games_raw.get("captain", False),
        ),
        goals=PlayerGoals(**{
            k: v for k, v in (stats_raw.get("goals") or {}).items()
            if k in PlayerGoals.model_fields
        }),
        shots=PlayerShots(**{
            k: v for k, v in (stats_raw.get("shots") or {}).items()
            if k in PlayerShots.model_fields
        }),
        passes=PlayerPasses(**{
            k: v for k, v in (stats_raw.get("passes") or {}).items()
            if k in PlayerPasses.model_fields
        }),
        tackles=PlayerTackles(**{
            k: v for k, v in (stats_raw.get("tackles") or {}).items()
            if k in PlayerTackles.model_fields
        }),
        duels=PlayerDuels(**{
            k: v for k, v in (stats_raw.get("duels") or {}).items()
            if k in PlayerDuels.model_fields
        }),
        dribbles=PlayerDribbles(**{
            k: v for k, v in (stats_raw.get("dribbles") or {}).items()
            if k in PlayerDribbles.model_fields
        }),
        cards=PlayerCards(**{
            k: v for k, v in (stats_raw.get("cards") or {}).items()
            if k in PlayerCards.model_fields
        }),
        penalty=PlayerPenalty(**{
            k: v for k, v in (stats_raw.get("penalty") or {}).items()
            if k in PlayerPenalty.model_fields
        }),
    )

    return Player(
        player_id=player_id,
        name=name,
        photo=player_photo_url(player_id),
        team_id=team["id"],
        team_name=team["name"],
        team_logo=team.get("logo", team_badge_url(team["id"])),
        nationality=nationality,
        country_code=country_code,
        position_code=games_raw.get("position", ""),
        stats=stats,
        fixture_id=fixture_id,
    )


# ---------------------------------------------------------------------------
# Lineups (formation data)
# ---------------------------------------------------------------------------

def fetch_fixture_lineups(fixture_id: int, matchweek: int) -> dict:
    """
    Fetch lineup/formation data for a fixture.
    Caches to data/2025-26/matchweek-{N}/lineups_{fixture_id}.json.
    """
    data_dir = matchweek_data_dir(matchweek)
    cache_path = data_dir / f"lineups_{fixture_id}.json"

    raw = load_json_cache(cache_path)
    if raw is None:
        data = _get("fixtures/lineups", {"fixture": fixture_id})
        raw = data.get("response", [])
        save_json_cache(cache_path, raw)
        print(f"  [Cache] Saved lineup data for fixture {fixture_id}")
    else:
        print(f"  [Cache] Loaded lineup data for fixture {fixture_id} from cache")

    # Return dict: {team_id: formation_string}
    result = {}
    for team_data in raw:
        team_id = team_data["team"]["id"]
        formation = team_data.get("formation", "")
        result[team_id] = formation
    return result


# ---------------------------------------------------------------------------
# High-level fetch commands
# ---------------------------------------------------------------------------

def fetch_all_matchweek_data(matchweek: int) -> dict:
    """
    Fetch complete data for a matchweek:
    1. All fixtures
    2. Player stats for each completed fixture
    3. Lineup/formation data for each completed fixture

    Returns summary dict with fixtures and total players.
    """
    print(f"\n{'='*50}")
    print(f"Fetching matchweek {matchweek} data")
    print(f"  {rate_limiter.status()}")
    print(f"{'='*50}")

    # Step 1: Fixtures
    fixtures = fetch_fixtures(matchweek)
    completed = [f for f in fixtures if f.is_complete]
    live = [f for f in fixtures if f.is_live]
    future = [f for f in fixtures if f.is_future]
    postponed = [f for f in fixtures if f.is_postponed]

    print(f"\nFixtures: {len(fixtures)} total | {len(completed)} complete | {len(live)} live | {len(future)} upcoming | {len(postponed)} postponed")

    if live:
        print("\n⚠️  Some matches are still in progress:")
        for f in live:
            print(f"  {f.home_team.name} {f.score_str} {f.away_team.name} ({f.status.elapsed}')")

    if future:
        print("\n📅 Upcoming matches:")
        for f in future:
            print(f"  {f.home_team.name} vs {f.away_team.name} — {f.date}")

    # Step 2 & 3: Player stats and lineups for completed fixtures
    all_players = []
    all_formations = {}

    for fixture in completed:
        print(f"\nFixture {fixture.fixture_id}: {fixture.home_team.name} {fixture.score_str} {fixture.away_team.name}")

        # Player stats
        players = fetch_fixture_players(fixture.fixture_id, matchweek)
        all_players.extend(players)
        print(f"  Players fetched: {len(players)}")

        # Lineups (formation)
        lineups = fetch_fixture_lineups(fixture.fixture_id, matchweek)
        for team_id, formation in lineups.items():
            all_formations[fixture.fixture_id] = all_formations.get(fixture.fixture_id, {})
            all_formations[fixture.fixture_id][team_id] = formation
        print(f"  Formations: {list(lineups.values())}")

    print(f"\n{'='*50}")
    print(f"Fetch complete: {len(all_players)} players across {len(completed)} fixtures")
    print(f"  {rate_limiter.status()}")
    print(f"{'='*50}\n")

    return {
        "matchweek": matchweek,
        "fixtures": [f.model_dump() for f in fixtures],
        "completed_count": len(completed),
        "live_count": len(live),
        "future_count": len(future),
        "player_count": len(all_players),
        "formations": all_formations,
    }


def check_matchweek_status(matchweek: int) -> dict:
    """
    Check if a matchweek is complete/incomplete/future.
    Only uses 1 API call (or 0 if cached).
    Returns status summary dict.
    """
    fixtures = fetch_fixtures(matchweek)

    completed = [f for f in fixtures if f.is_complete]
    live = [f for f in fixtures if f.is_live]
    future = [f for f in fixtures if f.is_future]
    postponed = [f for f in fixtures if f.is_postponed]

    active = [f for f in fixtures if not f.is_postponed]

    if len(completed) == len(active) and len(active) > 0:
        status = "complete"
    elif len(future) == len(active):
        status = "future"
    elif len(live) > 0:
        status = "live"
    else:
        status = "incomplete"

    return {
        "matchweek": matchweek,
        "status": status,
        "total": len(fixtures),
        "completed": len(completed),
        "live": len(live),
        "future": len(future),
        "postponed": len(postponed),
        "fixtures": [
            {
                "id": f.fixture_id,
                "home": f.home_team.name,
                "away": f.away_team.name,
                "score": f.score_str,
                "status": f.status.short,
                "date": f.date,
            }
            for f in fixtures
        ],
    }


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "get-current-round":
        print(f"\nCurrent round: {get_current_round()}")
        print(rate_limiter.status())

    elif command == "check-budget":
        print(f"\n{rate_limiter.status()}")

    elif command == "check-status":
        if len(sys.argv) < 3:
            print("Usage: python api_football.py check-status <matchweek>")
            sys.exit(1)
        matchweek = int(sys.argv[2])
        status = check_matchweek_status(matchweek)
        print(f"\nMatchweek {matchweek} status: {status['status'].upper()}")
        print(f"  {status['completed']}/{status['total']} matches complete")
        for f in status["fixtures"]:
            icon = "✅" if f["status"] in ("FT", "AET", "PEN") else "⏳" if f["status"] == "NS" else "🔴"
            print(f"  {icon} {f['home']} {f['score']} {f['away']} [{f['status']}]")
        print(f"\n{rate_limiter.status()}")

    elif command == "fetch-round":
        if len(sys.argv) < 3:
            print("Usage: python api_football.py fetch-round <matchweek>")
            sys.exit(1)
        matchweek = int(sys.argv[2])
        summary = fetch_all_matchweek_data(matchweek)
        print(json.dumps(summary, indent=2, default=str))

    elif command == "fetch-players":
        if len(sys.argv) < 3:
            print("Usage: python api_football.py fetch-players <fixture_id> [matchweek]")
            sys.exit(1)
        fixture_id = int(sys.argv[2])
        matchweek = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        if matchweek == 0:
            # Try to infer from current round
            rnd = get_current_round()
            matchweek = matchweek_from_round(rnd)
        players = fetch_fixture_players(fixture_id, matchweek)
        print(f"\nFetched {len(players)} players for fixture {fixture_id}")
        for p in players:
            print(f"  {p.name} ({p.team_name}) — {p.stats.minutes_played}' | Goals: {p.stats.goals_scored} | Assists: {p.stats.assists}")
        print(f"\n{rate_limiter.status()}")

    elif command == "fetch-lineups":
        if len(sys.argv) < 3:
            print("Usage: python api_football.py fetch-lineups <fixture_id> [matchweek]")
            sys.exit(1)
        fixture_id = int(sys.argv[2])
        matchweek = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        if matchweek == 0:
            rnd = get_current_round()
            matchweek = matchweek_from_round(rnd)
        lineups = fetch_fixture_lineups(fixture_id, matchweek)
        print(f"\nLineups for fixture {fixture_id}:")
        for team_id, formation in lineups.items():
            print(f"  Team {team_id}: {formation}")
        print(f"\n{rate_limiter.status()}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
