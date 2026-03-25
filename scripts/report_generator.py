"""
Report Generator for the EPL TOTW Builder.

Generates markdown reports from TOTW analysis:
- output/matchweek-{N}/analysis/formation_report.md  — Formation analysis narrative
- output/matchweek-{N}/analysis/totw_report.md        — Full TOTW summary table
- output/matchweek-{N}/analysis/player_{id}.md        — Per-player detail reports

CLI:
    python scripts/report_generator.py 30
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_models import SelectedFormation, TOTWPlayer, TOTWSelection
from scripts.utils import (
    load_json_cache,
    load_text_cache,
    matchweek_analysis_dir,
    matchweek_data_dir,
    save_text_cache,
)


def load_formation(matchweek: int) -> SelectedFormation:
    path = matchweek_analysis_dir(matchweek) / "formation.json"
    data = load_json_cache(path)
    if not data:
        raise FileNotFoundError(f"No formation.json for matchweek {matchweek}. Run formation_analyzer.py first.")
    return SelectedFormation(**data)


def load_totw(matchweek: int) -> TOTWSelection:
    path = matchweek_analysis_dir(matchweek) / "players.json"
    data = load_json_cache(path)
    if not data:
        raise FileNotFoundError(f"No players.json for matchweek {matchweek}. Run player_evaluator.py first.")
    return TOTWSelection(**data)


def load_commentary(matchweek: int, fixture_id: int) -> str:
    """Load cached match commentary text if available."""
    path = matchweek_data_dir(matchweek) / "commentaries" / f"{fixture_id}_commentary.txt"
    return load_text_cache(path) or ""


def load_match_report(matchweek: int, fixture_id: int) -> str:
    """Load cached match report text if available."""
    path = matchweek_data_dir(matchweek) / "reports" / f"{fixture_id}_report.txt"
    return load_text_cache(path) or ""


def _fixture_summary(totw: TOTWSelection) -> str:
    """Build a fixture results section for the report."""
    # Load fixtures to get all results
    from scripts.utils import matchweek_data_dir
    fixtures_path = matchweek_data_dir(totw.matchweek) / "fixtures.json"
    fixtures = load_json_cache(fixtures_path) or []

    lines = ["| Home Team | Score | Away Team | Result |",
             "|-----------|-------|-----------|--------|"]
    for f in fixtures:
        status = f["fixture"]["status"]["short"]
        if status not in ("FT", "AET", "PEN"):
            continue
        home = f["teams"]["home"]
        away = f["teams"]["away"]
        score = f["score"]["fulltime"]
        h_goals = score.get("home", "?")
        a_goals = score.get("away", "?")
        if home.get("winner"):
            result = f"**{home['name']} win**"
        elif away.get("winner"):
            result = f"**{away['name']} win**"
        else:
            result = "Draw"
        lines.append(f"| {home['name']} | {h_goals}–{a_goals} | {away['name']} | {result} |")
    return "\n".join(lines)


def generate_formation_report(matchweek: int, formation: SelectedFormation) -> str:
    """Generate the formation analysis markdown report."""
    lines = [
        f"# Formation Report — Matchweek {matchweek}",
        "",
        f"## Selected Formation: {formation.formation}",
        "",
        f"**Status**: {'Default (fallback)' if formation.is_default else 'Selected from match data'}",
        "",
        f"**Rationale**: {formation.rationale}",
        "",
        "## Formation Usage Breakdown",
        "",
        "| Formation | Times Used | Wins | Goals Scored | Winning Teams |",
        "|-----------|-----------|------|-------------|---------------|",
    ]

    for fu in sorted(formation.usages, key=lambda u: u.win_count, reverse=True):
        teams_str = ", ".join(fu.teams) if fu.teams else "—"
        lines.append(
            f"| {fu.formation} | {fu.usage_count} | {fu.win_count} | {fu.goals_scored} | {teams_str} |"
        )

    lines += [
        "",
        f"## Position Slots in {formation.formation}",
        "",
        f"**{len(formation.positions)} positions**: {', '.join(formation.positions)}",
        "",
        "## Formation Analysis",
        "",
    ]

    if formation.is_default:
        lines += [
            f"No formation emerged as a clear winner this matchweek. {formation.rationale}",
            "",
            "The classic **4-3-3** provides the ideal balance of defensive solidity and attacking width, "
            "making it the perfect fallback for a mixed matchweek.",
        ]
    else:
        # Count non-default wins by formation
        winner_fus = [fu for fu in formation.usages if fu.formation == formation.formation]
        if winner_fus:
            fu = winner_fus[0]
            lines += [
                f"The **{formation.formation}** was the dominant tactical setup this matchweek, "
                f"used by {fu.usage_count} teams and delivering {fu.win_count} victories.",
                "",
                f"Teams using this formation scored {fu.goals_scored} goals in total, "
                f"highlighting its effectiveness going forward.",
                "",
            ]
            if fu.teams:
                lines.append(f"Winning sides: **{', '.join(fu.teams)}**.")

    return "\n".join(lines)


def generate_player_report(matchweek: int, tp: TOTWPlayer) -> str:
    """Generate a detailed markdown report for a single TOTW player."""
    p = tp.player
    s = p.stats

    result_str = {"win": "WIN", "draw": "DRAW", "loss": "LOSS"}.get(p.fixture_result or "", "")

    # Try to load commentary for context
    commentary = load_commentary(matchweek, p.fixture_id)
    report_text = load_match_report(matchweek, p.fixture_id)

    lines = [
        f"# Player Report: {p.name}",
        f"**Position**: {tp.position_slot} | **Team**: {p.team_name} | **Match Result**: {result_str}",
        "",
        f"## Key Stats",
        "",
        "| Stat | Value |",
        "|------|-------|",
        f"| Minutes Played | {s.minutes_played} |",
        f"| Rating | {s.games.rating or 'N/A'} |",
        f"| Goals | {s.goals_scored} |",
        f"| Assists | {s.assists} |",
        f"| Shots on Target | {s.shots_on_target} |",
        f"| Key Passes | {s.key_passes} |",
        f"| Tackles | {s.tackles_won} |",
        f"| Interceptions | {s.interceptions} |",
        f"| Dribbles Completed | {s.dribbles_completed} |",
        f"| Pass Accuracy | {s.pass_accuracy:.0f}% |",
    ]

    if p.position_code == "G":
        lines += [
            f"| Saves | {s.saves} |",
            f"| Goals Conceded | {s.goals.conceded or 0} |",
            f"| Clean Sheet | {'Yes' if s.clean_sheet else 'No'} |",
        ]

    lines += [
        "",
        f"## Key Stat",
        f"**{tp.key_stat}**",
        "",
        f"## Why Selected",
        "",
        tp.selection_reason,
    ]

    if report_text:
        lines += [
            "",
            "## Match Report Excerpt",
            "",
            report_text[:1000] + ("..." if len(report_text) > 1000 else ""),
        ]

    if commentary:
        # Try to find lines mentioning the player's name
        player_last = p.name.split()[-1]
        relevant = [
            line for line in commentary.splitlines()
            if player_last.lower() in line.lower()
        ][:5]
        if relevant:
            lines += [
                "",
                "## Match Commentary",
                "",
                *[f"> {line.strip()}" for line in relevant],
            ]

    return "\n".join(lines)


def generate_totw_summary(matchweek: int, totw: TOTWSelection) -> str:
    """Generate the full TOTW summary markdown report."""
    lines = [
        f"# Premier League — Team of the Week",
        f"## Matchweek {matchweek} | {totw.season} Season",
        "",
        f"**Formation**: {totw.formation.formation}",
        f"**Formation rationale**: {totw.formation.rationale}",
        "",
        "## Matchweek Results",
        "",
        _fixture_summary(totw),
        "",
        "## Starting XI",
        "",
        "| Position | Player | Team | Rating | Key Stat |",
        "|----------|--------|------|--------|----------|",
    ]

    for tp in totw.players:
        p = tp.player
        rating = p.stats.games.rating or "N/A"
        lines.append(
            f"| {tp.position_slot} | {p.name} | {p.team_name} | {rating} | {tp.key_stat} |"
        )

    lines += [
        "",
        "## Formation",
        "",
        f"```",
        _ascii_formation(totw),
        f"```",
        "",
        "## Player Highlights",
        "",
    ]

    for tp in totw.players:
        p = tp.player
        lines += [
            f"### {tp.position_slot} — {p.name} ({p.team_name})",
            f"{tp.selection_reason}",
            f"**Key stat**: {tp.key_stat}",
            "",
        ]

    return "\n".join(lines)


def _ascii_formation(totw: TOTWSelection) -> str:
    """Draw a simple ASCII representation of the formation."""
    # Group players by rough position line
    gk = [tp for tp in totw.players if tp.position_slot == "GK"]
    defenders = [tp for tp in totw.players if tp.position_slot in ("RB", "CB", "LB", "RWB", "LWB")]
    def_mids = [tp for tp in totw.players if tp.position_slot == "CDM"]
    mids = [tp for tp in totw.players if tp.position_slot in ("CM", "RM", "LM", "CAM")]
    attackers = [tp for tp in totw.players if tp.position_slot in ("RW", "LW", "ST", "CF")]

    width = 60
    sep = "-" * width

    def center_row(players: list[TOTWPlayer]) -> str:
        if not players:
            return ""
        names = [f"{tp.position_slot}:{tp.player.name.split()[-1]}" for tp in players]
        spacing = width // (len(names) + 1)
        return "  ".join(n.center(spacing) for n in names)

    rows = [
        sep,
        center_row(attackers),
        center_row(mids),
        center_row(def_mids),
        center_row(defenders),
        center_row(gk),
        sep,
    ]
    return "\n".join(r for r in rows if r)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/report_generator.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"Generating reports for matchweek {matchweek}...")

    formation = load_formation(matchweek)
    totw = load_totw(matchweek)
    out_dir = matchweek_analysis_dir(matchweek)

    # 1. Formation report
    form_report = generate_formation_report(matchweek, formation)
    form_path = out_dir / "formation_report.md"
    save_text_cache(form_path, form_report)
    print(f"  Saved formation report → {form_path}")

    # 2. TOTW summary report
    totw_report = generate_totw_summary(matchweek, totw)
    totw_path = out_dir / "totw_report.md"
    save_text_cache(totw_path, totw_report)
    print(f"  Saved TOTW report → {totw_path}")

    # 3. Per-player reports
    for tp in totw.players:
        player_report = generate_player_report(matchweek, tp)
        player_path = out_dir / f"player_{tp.player.player_id}.md"
        save_text_cache(player_path, player_report)

    print(f"  Saved {len(totw.players)} player reports → {out_dir}/player_*.md")

    # Print the summary
    print()
    print(totw_report[:2000])
    if len(totw_report) > 2000:
        print(f"\n... (truncated, full report at {totw_path})")


if __name__ == "__main__":
    main()
