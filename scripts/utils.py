"""
Shared utilities for the EPL TOTW Builder.
- API rate limiter (100 req/day for API-Football)
- File-based caching
- Path helpers
- Country code mappings
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

# Load secrets from .claude/settings.local.json if not already in env
_settings_local = Path(__file__).parent.parent / ".claude" / "settings.local.json"
if _settings_local.exists():
    try:
        _local = json.loads(_settings_local.read_text())
        for _k, _v in _local.get("env", {}).items():
            if _k not in os.environ and _v:
                os.environ[_k] = _v
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
TEMPLATES_DIR = ROOT / "templates"
SCRIPTS_DIR = ROOT / "scripts"

SEASON = "2025-26"
USAGE_FILE = DATA_DIR / ".api_usage.json"


def matchweek_data_dir(matchweek: int) -> Path:
    p = DATA_DIR / SEASON / f"matchweek-{matchweek}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def matchweek_output_dir(matchweek: int) -> Path:
    p = OUTPUT_DIR / f"matchweek-{matchweek}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def matchweek_analysis_dir(matchweek: int) -> Path:
    p = matchweek_output_dir(matchweek) / "analysis"
    p.mkdir(parents=True, exist_ok=True)
    return p


def matchweek_reports_dir(matchweek: int) -> Path:
    p = matchweek_data_dir(matchweek) / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def matchweek_commentaries_dir(matchweek: int) -> Path:
    p = matchweek_data_dir(matchweek) / "commentaries"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# File caching
# ---------------------------------------------------------------------------

def cache_exists(path: Path) -> bool:
    """Return True if a non-empty cache file exists."""
    return path.exists() and path.stat().st_size > 10


def load_json_cache(path: Path) -> dict | list | None:
    """Load JSON from cache file. Returns None if not found or invalid."""
    if not cache_exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_json_cache(path: Path, data: dict | list) -> None:
    """Save data as JSON to cache file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_text_cache(path: Path, text: str) -> None:
    """Save text content to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_text_cache(path: Path) -> str | None:
    """Load text from file. Returns None if not found."""
    if not cache_exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


# ---------------------------------------------------------------------------
# API rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Tracks API-Football daily usage (100 requests/day limit).
    Usage is stored in data/.api_usage.json keyed by date.
    """

    DAILY_LIMIT = 100

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if USAGE_FILE.exists():
            try:
                with open(USAGE_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self) -> None:
        with open(USAGE_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def today(self) -> str:
        return date.today().isoformat()

    @property
    def used_today(self) -> int:
        return self._data.get(self.today, 0)

    @property
    def remaining_today(self) -> int:
        return max(0, self.DAILY_LIMIT - self.used_today)

    @property
    def can_make_request(self) -> bool:
        return self.used_today < self.DAILY_LIMIT

    def record_request(self) -> None:
        """Call after each successful API request."""
        today = self.today
        self._data[today] = self._data.get(today, 0) + 1
        self._save()

    def check_budget(self, planned_requests: int) -> bool:
        """Returns True if enough budget remains for planned_requests."""
        return self.remaining_today >= planned_requests

    def status(self) -> str:
        return (
            f"API-Football usage today ({self.today}): "
            f"{self.used_today}/{self.DAILY_LIMIT} "
            f"({self.remaining_today} remaining)"
        )


# Singleton rate limiter instance
rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# API-Football CDN helpers
# ---------------------------------------------------------------------------

def team_badge_url(team_id: int) -> str:
    return f"https://media.api-sports.io/football/teams/{team_id}.png"


def player_photo_url(player_id: int) -> str:
    return f"https://media.api-sports.io/football/players/{player_id}.png"


def flag_url(country_code: str) -> str:
    return f"https://media.api-sports.io/flags/{country_code}.svg"


# ---------------------------------------------------------------------------
# Country → ISO code mapping
# API-Football uses nationality strings; we need ISO codes for flags
# ---------------------------------------------------------------------------

COUNTRY_TO_CODE: dict[str, str] = {
    "England": "gb-eng",
    "Scotland": "gb-sct",
    "Wales": "gb-wls",
    "Northern Ireland": "gb-nir",
    "Republic of Ireland": "ie",
    "Ireland": "ie",
    "France": "fr",
    "Germany": "de",
    "Spain": "es",
    "Portugal": "pt",
    "Brazil": "br",
    "Argentina": "ar",
    "Netherlands": "nl",
    "Belgium": "be",
    "Italy": "it",
    "Denmark": "dk",
    "Sweden": "se",
    "Norway": "no",
    "Switzerland": "ch",
    "Austria": "at",
    "Poland": "pl",
    "Czech Republic": "cz",
    "Slovakia": "sk",
    "Croatia": "hr",
    "Serbia": "rs",
    "Slovenia": "si",
    "Hungary": "hu",
    "Romania": "ro",
    "Bulgaria": "bg",
    "Greece": "gr",
    "Turkey": "tr",
    "Russia": "ru",
    "Ukraine": "ua",
    "Morocco": "ma",
    "Senegal": "sn",
    "Ivory Coast": "ci",
    "Ghana": "gh",
    "Nigeria": "ng",
    "Cameroon": "cm",
    "Egypt": "eg",
    "Algeria": "dz",
    "Tunisia": "tn",
    "Mali": "ml",
    "Guinea": "gn",
    "Gabon": "ga",
    "Congo DR": "cd",
    "South Africa": "za",
    "Colombia": "co",
    "Uruguay": "uy",
    "Chile": "cl",
    "Mexico": "mx",
    "United States": "us",
    "Canada": "ca",
    "Australia": "au",
    "New Zealand": "nz",
    "Japan": "jp",
    "South Korea": "kr",
    "China": "cn",
    "Saudi Arabia": "sa",
    "Qatar": "qa",
    "Iran": "ir",
    "Israel": "il",
    "Ecuador": "ec",
    "Peru": "pe",
    "Venezuela": "ve",
    "Paraguay": "py",
    "Bolivia": "bo",
    "Costa Rica": "cr",
    "Honduras": "hn",
    "Jamaica": "jm",
    "Trinidad and Tobago": "tt",
    "Iceland": "is",
    "Finland": "fi",
    "Slovakia": "sk",
    "North Macedonia": "mk",
    "Albania": "al",
    "Kosovo": "xk",
    "Bosnia and Herzegovina": "ba",
    "Montenegro": "me",
    "Georgia": "ge",
    "Armenia": "am",
    "Azerbaijan": "az",
    "Kazakhstan": "kz",
}


def get_country_code(nationality: str) -> str:
    """Return ISO country code for flag URL. Falls back to 'xx' if unknown."""
    return COUNTRY_TO_CODE.get(nationality, nationality[:2].lower())


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def parse_fixture_date(date_str: str) -> datetime:
    """Parse ISO datetime string from API-Football."""
    try:
        # Handle timezone offset format
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromisoformat(date_str[:19])


def format_fixture_date(date_str: str, fmt: str = "%a %d %b %Y, %H:%M") -> str:
    """Format fixture date for display (e.g. 'Sat 15 Mar 2025, 15:00')."""
    try:
        dt = parse_fixture_date(date_str)
        return dt.strftime(fmt)
    except (ValueError, AttributeError):
        return date_str


def round_string(matchweek: int) -> str:
    """Return the API-Football round string for a matchweek number."""
    return f"Regular Season - {matchweek}"


def matchweek_from_round(round_str: str) -> int:
    """Extract matchweek number from round string like 'Regular Season - 30'."""
    try:
        return int(round_str.split(" - ")[-1])
    except (ValueError, IndexError):
        return 0
