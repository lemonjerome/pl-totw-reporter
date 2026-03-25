"""
Formation Analyzer for the EPL TOTW Builder.

Loads cached lineup data for a matchweek, counts formation usage by winning teams,
and selects the best formation (or defaults to 4-3-3 if no clear winner).

CLI:
    python scripts/formation_analyzer.py 30
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_models import FormationUsage, SelectedFormation
from scripts.utils import (
    load_json_cache,
    matchweek_analysis_dir,
    matchweek_data_dir,
    save_json_cache,
)

DEFAULT_FORMATION = "4-3-3"


def load_fixtures(matchweek: int) -> list[dict]:
    """Load cached fixtures for the matchweek."""
    path = matchweek_data_dir(matchweek) / "fixtures.json"
    data = load_json_cache(path)
    if not data:
        raise FileNotFoundError(
            f"No fixtures cache found for matchweek {matchweek}. "
            f"Run: python scripts/api_football.py fetch-round {matchweek}"
        )
    return data


def load_lineups(matchweek: int, fixture_id: int) -> list[dict] | None:
    """Load cached lineup data for a single fixture."""
    path = matchweek_data_dir(matchweek) / f"lineups_{fixture_id}.json"
    return load_json_cache(path)


def get_fixture_winner(fixture: dict) -> str | None:
    """Return 'home', 'away', or None (draw) based on fixture data."""
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    if home.get("winner"):
        return "home"
    if away.get("winner"):
        return "away"
    return None  # draw or incomplete


def get_fixture_score(fixture: dict) -> tuple[int, int]:
    """Return (home_goals, away_goals) from fulltime score."""
    score = fixture["score"]["fulltime"]
    return score.get("home") or 0, score.get("away") or 0


def analyze_formations(matchweek: int) -> SelectedFormation:
    """
    Analyze formation usage across a matchweek.

    Returns a SelectedFormation with the best formation (most wins)
    or 4-3-3 default if no clear winner.
    """
    fixtures = load_fixtures(matchweek)

    # formation -> FormationUsage aggregator
    usage_map: dict[str, FormationUsage] = {}

    for fixture in fixtures:
        status = fixture["fixture"]["status"]["short"]
        if status not in ("FT", "AET", "PEN"):
            continue  # skip incomplete

        fixture_id = fixture["fixture"]["id"]
        home_team = fixture["teams"]["home"]
        away_team = fixture["teams"]["away"]
        home_goals, away_goals = get_fixture_score(fixture)
        winner = get_fixture_winner(fixture)

        lineups = load_lineups(matchweek, fixture_id)
        if not lineups:
            continue

        for team_lineup in lineups:
            formation = team_lineup.get("formation", "").strip()
            if not formation:
                continue

            team_name = team_lineup["team"]["name"]
            team_id = team_lineup["team"]["id"]

            # Determine if this team won and how many goals they scored
            if team_id == home_team["id"]:
                team_won = winner == "home"
                goals = home_goals
            else:
                team_won = winner == "away"
                goals = away_goals

            if formation not in usage_map:
                usage_map[formation] = FormationUsage(formation=formation)

            fu = usage_map[formation]
            fu.usage_count += 1
            fu.goals_scored += goals
            if team_won:
                fu.win_count += 1
                # Only add winning teams to the teams list (for rationale display)
                if team_name not in fu.teams:
                    fu.teams.append(team_name)
            else:
                pass  # non-winners tracked via usage_count only

    usages = list(usage_map.values())

    if not usages:
        return SelectedFormation(
            formation=DEFAULT_FORMATION,
            is_default=True,
            rationale="No lineup data found. Defaulting to 4-3-3.",
            usages=[],
        )

    # Sort by wins descending, then goals as tiebreaker
    usages.sort(key=lambda u: (u.win_count, u.goals_scored), reverse=True)

    top = usages[0]

    # Check for a clear winner (more wins than the second-best)
    if len(usages) > 1 and top.win_count == usages[1].win_count:
        # Tied on wins — compare goals
        if top.goals_scored == usages[1].goals_scored:
            # No clear winner — default
            return SelectedFormation(
                formation=DEFAULT_FORMATION,
                is_default=True,
                rationale=(
                    f"No formation stood out — {top.formation} and {usages[1].formation} "
                    f"tied on wins ({top.win_count}) and goals ({top.goals_scored}). "
                    f"Defaulting to 4-3-3."
                ),
                usages=usages,
            )
        # Tied on wins but top has more goals — use it
        rationale = (
            f"{top.formation} wins: used by winning teams {top.win_count} time(s) and "
            f"outscored {usages[1].formation} ({top.goals_scored} vs {usages[1].goals_scored} goals)."
        )
    elif top.win_count == 0:
        # No team won using any formation (all draws)
        return SelectedFormation(
            formation=DEFAULT_FORMATION,
            is_default=True,
            rationale=(
                "No team won using a single dominant formation this matchweek "
                f"(most used: {top.formation} — {top.win_count} wins). Defaulting to 4-3-3."
            ),
            usages=usages,
        )
    else:
        rationale = (
            f"{top.formation} was the most successful formation this matchweek — "
            f"used by {top.win_count} winning team(s): {', '.join(top.teams[:3])}."
        )

    return SelectedFormation(
        formation=top.formation,
        is_default=False,
        rationale=rationale,
        usages=usages,
    )


def save_formation_result(matchweek: int, result: SelectedFormation) -> Path:
    """Save formation analysis result to output directory."""
    out_dir = matchweek_analysis_dir(matchweek)
    path = out_dir / "formation.json"
    save_json_cache(path, result.model_dump())
    return path


def print_formation_report(result: SelectedFormation) -> None:
    """Print a summary of the formation analysis."""
    print(f"\n{'='*60}")
    print(f"FORMATION ANALYSIS")
    print(f"{'='*60}")
    print(f"Selected: {result.formation}")
    if result.is_default:
        print(f"Status:   DEFAULT (fallback)")
    else:
        print(f"Status:   SELECTED (from match data)")
    print(f"Rationale: {result.rationale}")

    if result.usages:
        print(f"\nFormation Usage Breakdown:")
        print(f"{'Formation':<16} {'Used':>5} {'Wins':>5} {'Goals':>6}  Teams")
        print("-" * 70)
        for fu in sorted(result.usages, key=lambda u: u.win_count, reverse=True):
            teams_str = ", ".join(fu.teams[:3])
            if len(fu.teams) > 3:
                teams_str += f" +{len(fu.teams)-3} more"
            print(f"{fu.formation:<16} {fu.usage_count:>5} {fu.win_count:>5} {fu.goals_scored:>6}  {teams_str}")

    positions = result.positions
    print(f"\nPosition slots ({len(positions)}):")
    print("  " + ", ".join(positions))
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/formation_analyzer.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"Analyzing formations for matchweek {matchweek}...")

    result = analyze_formations(matchweek)
    out_path = save_formation_result(matchweek, result)
    print_formation_report(result)
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
