"""
Data models for the EPL TOTW Builder.
All data flowing through the pipeline uses these Pydantic models.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fixture / Match models
# ---------------------------------------------------------------------------

class TeamInfo(BaseModel):
    id: int
    name: str
    logo: str  # URL to badge image


class Score(BaseModel):
    home: Optional[int] = None
    away: Optional[int] = None


class FixtureStatus(BaseModel):
    short: str   # FT, NS, 1H, HT, 2H, AET, PEN, PST, CANC, etc.
    long: str    # "Match Finished", "Not Started", etc.
    elapsed: Optional[int] = None  # minutes played


class Fixture(BaseModel):
    fixture_id: int
    date: str            # ISO datetime string
    round: str           # e.g. "Regular Season - 30"
    home_team: TeamInfo
    away_team: TeamInfo
    score: Score
    status: FixtureStatus

    @property
    def is_complete(self) -> bool:
        return self.status.short in ("FT", "AET", "PEN")

    @property
    def is_live(self) -> bool:
        return self.status.short in ("1H", "HT", "2H", "ET", "BT", "P")

    @property
    def is_future(self) -> bool:
        return self.status.short == "NS"

    @property
    def is_postponed(self) -> bool:
        return self.status.short in ("PST", "CANC", "ABD", "SUSP")

    @property
    def result(self) -> Optional[str]:
        """Returns 'home', 'away', or 'draw' for completed fixtures."""
        if not self.is_complete:
            return None
        if self.score.home is None or self.score.away is None:
            return None
        if self.score.home > self.score.away:
            return "home"
        elif self.score.away > self.score.home:
            return "away"
        return "draw"

    @property
    def winner_team(self) -> Optional[TeamInfo]:
        r = self.result
        if r == "home":
            return self.home_team
        if r == "away":
            return self.away_team
        return None

    @property
    def score_str(self) -> str:
        h = self.score.home if self.score.home is not None else "-"
        a = self.score.away if self.score.away is not None else "-"
        return f"{h} - {a}"


# ---------------------------------------------------------------------------
# Player stat models
# ---------------------------------------------------------------------------

class PlayerGames(BaseModel):
    minutes: Optional[int] = None
    position: Optional[str] = None   # G, D, M, F
    rating: Optional[str] = None
    captain: bool = False


class PlayerGoals(BaseModel):
    total: Optional[int] = None
    conceded: Optional[int] = None
    assists: Optional[int] = None
    saves: Optional[int] = None


class PlayerShots(BaseModel):
    total: Optional[int] = None
    on: Optional[int] = None


class PlayerPasses(BaseModel):
    total: Optional[int] = None
    key: Optional[int] = None
    accuracy: Optional[str] = None        # "87" (percent)
    accurate_crosses: Optional[int] = None  # accurateCross (SofaScore)


class PlayerTackles(BaseModel):
    total: Optional[int] = None          # wonTackle (SofaScore)
    blocks: Optional[int] = None         # outfielderBlock
    interceptions: Optional[int] = None  # interceptionWon
    clearances: Optional[int] = None     # totalClearance


class PlayerDuels(BaseModel):
    total: Optional[int] = None
    won: Optional[int] = None
    aerial_won: Optional[int] = None   # aerialWon
    aerial_lost: Optional[int] = None  # aerialLost


class PlayerDribbles(BaseModel):
    attempts: Optional[int] = None
    success: Optional[int] = None


class PlayerCards(BaseModel):
    yellow: int = 0
    red: int = 0


class PlayerPenalty(BaseModel):
    won: Optional[int] = None
    committed: Optional[int] = None
    scored: Optional[int] = None
    missed: Optional[int] = None
    saved: Optional[int] = None


class PlayerStats(BaseModel):
    games: PlayerGames = Field(default_factory=PlayerGames)
    goals: PlayerGoals = Field(default_factory=PlayerGoals)
    shots: PlayerShots = Field(default_factory=PlayerShots)
    passes: PlayerPasses = Field(default_factory=PlayerPasses)
    tackles: PlayerTackles = Field(default_factory=PlayerTackles)
    duels: PlayerDuels = Field(default_factory=PlayerDuels)
    dribbles: PlayerDribbles = Field(default_factory=PlayerDribbles)
    cards: PlayerCards = Field(default_factory=PlayerCards)
    penalty: PlayerPenalty = Field(default_factory=PlayerPenalty)

    @property
    def minutes_played(self) -> int:
        return self.games.minutes or 0

    @property
    def goals_scored(self) -> int:
        return self.goals.total or 0

    @property
    def assists(self) -> int:
        return self.goals.assists or 0

    @property
    def goal_contributions(self) -> int:
        return self.goals_scored + self.assists

    @property
    def saves(self) -> int:
        return self.goals.saves or 0

    @property
    def clean_sheet(self) -> bool:
        return (self.goals.conceded or 0) == 0

    @property
    def shots_on_target(self) -> int:
        return self.shots.on or 0

    @property
    def key_passes(self) -> int:
        return self.passes.key or 0

    @property
    def tackles_won(self) -> int:
        return self.tackles.total or 0

    @property
    def interceptions(self) -> int:
        return self.tackles.interceptions or 0

    @property
    def clearances(self) -> int:
        return self.tackles.clearances or 0

    @property
    def aerial_duels_won(self) -> int:
        return self.duels.aerial_won or 0

    @property
    def accurate_crosses(self) -> int:
        return self.passes.accurate_crosses or 0

    @property
    def defensive_actions(self) -> int:
        return self.tackles_won + self.interceptions

    @property
    def dribbles_completed(self) -> int:
        return self.dribbles.success or 0

    @property
    def duels_won(self) -> int:
        return self.duels.won or 0

    @property
    def pass_accuracy(self) -> float:
        try:
            return float(self.passes.accuracy or 0)
        except (ValueError, TypeError):
            return 0.0

    @property
    def shot_conversion(self) -> float:
        total = self.shots.total or 0
        if total == 0:
            return 0.0
        return round((self.goals_scored / total) * 100, 1)

    @property
    def rating_float(self) -> float:
        try:
            return float(self.games.rating or 0)
        except (ValueError, TypeError):
            return 0.0


class Player(BaseModel):
    player_id: int
    name: str
    photo: str           # URL to player photo
    team_id: int
    team_name: str
    team_logo: str       # URL to team badge
    nationality: str
    country_code: str    # ISO code for flag (e.g. "gb-eng", "fr", "br")
    position_code: str   # G, D, M, F (from API)
    specific_position: Optional[str] = None  # e.g. "GK", "CB", "ST", "RM" — inferred from formation
    grid_position: Optional[str] = None  # e.g. "1:1" from lineup data
    stats: PlayerStats = Field(default_factory=PlayerStats)
    fixture_id: int = 0
    fixture_result: Optional[str] = None   # "home_win", "away_win", "draw", "loss"

    @property
    def photo_url(self) -> str:
        # Use stored photo URL if available (e.g. Understat for soccerdata players)
        if self.photo:
            return self.photo
        return f"https://media.api-sports.io/football/players/{self.player_id}.png"

    @property
    def flag_url(self) -> str:
        if self.country_code and self.country_code != "xx":
            return f"https://media.api-sports.io/flags/{self.country_code}.svg"
        return ""

    @property
    def team_badge_url(self) -> str:
        # Use stored team logo if available (e.g. PL CDN for soccerdata players)
        if self.team_logo:
            return self.team_logo
        return f"https://media.api-sports.io/football/teams/{self.team_id}.png"

    @property
    def is_eligible(self) -> bool:
        """Player must have played at least 60 minutes."""
        return self.stats.minutes_played >= 60


# ---------------------------------------------------------------------------
# Formation model
# ---------------------------------------------------------------------------

class FormationUsage(BaseModel):
    formation: str          # e.g. "4-3-3"
    usage_count: int = 0    # total times used in matchweek
    win_count: int = 0      # times used by winning teams
    goals_scored: int = 0   # total goals by teams using this formation
    teams: list[str] = Field(default_factory=list)  # team names that used it


class SelectedFormation(BaseModel):
    formation: str               # e.g. "4-3-3"
    is_default: bool = False     # True if no clear winner (fallback to 4-3-3)
    rationale: str = ""          # explanation
    usages: list[FormationUsage] = Field(default_factory=list)

    @property
    def positions(self) -> list[str]:
        """Return the list of position slots for this formation."""
        FORMATION_POSITIONS = {
            "4-3-3":   ["GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CM", "RW", "ST", "LW"],
            "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "RM", "CAM", "LM", "ST"],
            "4-4-2":   ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
            "4-1-4-1": ["GK", "RB", "CB", "CB", "LB", "CDM", "RM", "CM", "CM", "LM", "ST"],
            "3-5-2":   ["GK", "CB", "CB", "CB", "RWB", "CM", "CM", "CM", "LWB", "ST", "ST"],
            "3-4-3":   ["GK", "CB", "CB", "CB", "RWB", "CM", "CM", "LWB", "RW", "ST", "LW"],
            "5-3-2":   ["GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CM", "ST", "ST"],
            "4-4-2 Diamond": ["GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CM", "CAM", "ST", "ST"],
        }
        return FORMATION_POSITIONS.get(self.formation, FORMATION_POSITIONS["4-3-3"])


# ---------------------------------------------------------------------------
# TOTW Selection model
# ---------------------------------------------------------------------------

class TOTWPlayer(BaseModel):
    position_slot: str   # e.g. "GK", "RB", "CB", "LW"
    player: Player
    selection_reason: str = ""
    key_stat: str = ""   # e.g. "2 goals, 1 assist"


class TOTWSelection(BaseModel):
    matchweek: int
    season: str = "2025-26"
    formation: SelectedFormation
    players: list[TOTWPlayer] = Field(default_factory=list)   # 11 players

    @property
    def starting_xi(self) -> dict[str, Player]:
        return {p.position_slot: p.player for p in self.players}

    def get_player(self, position: str) -> Optional[TOTWPlayer]:
        for p in self.players:
            if p.position_slot == position:
                return p
        return None
