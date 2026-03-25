"""
Team Diagram Renderer for the EPL TOTW Builder.

Renders the TOTW team formation diagram as a PNG:
1. Loads TOTW selection from output/matchweek-{N}/analysis/players.json
2. Maps players to pitch coordinates using formation coordinate maps
3. Renders templates/pitch.html via Jinja2 → HTML string
4. Screenshots the HTML page via Playwright → PNG

Output: output/matchweek-{N}/totw_diagram.png

CLI:
    python scripts/diagram_renderer.py 30
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jinja2 import Environment, FileSystemLoader

from scripts.data_models import SelectedFormation, TOTWSelection
from scripts.utils import (
    load_json_cache,
    matchweek_analysis_dir,
    matchweek_output_dir,
    save_json_cache,
)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# ---------------------------------------------------------------------------
# Formation coordinate maps
# x = left-to-right %, y = top-to-bottom % (GK near bottom, attackers near top)
# Adjusted to fit inside the pitch with the 52px header
# ---------------------------------------------------------------------------

FORMATION_COORDS: dict[str, dict[str, list[dict]]] = {
    "4-3-3": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 73}],
        "CB":  [{"x": 35, "y": 73}, {"x": 65, "y": 73}],
        "LB":  [{"x": 12, "y": 73}],
        "CDM": [{"x": 50, "y": 57}],
        "CM":  [{"x": 30, "y": 44}, {"x": 70, "y": 44}],
        "RW":  [{"x": 88, "y": 26}],
        "ST":  [{"x": 50, "y": 18}],
        "LW":  [{"x": 12, "y": 26}],
    },
    # 4-2-3-1: double pivot + 3 attacking mids (RM, CAM, LM) + lone ST
    # The "3" are midfielders connected to each other; ST is alone
    "4-2-3-1": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 36, "y": 59}, {"x": 64, "y": 59}],
        "RM":  [{"x": 88, "y": 40}],
        "CAM": [{"x": 50, "y": 38}],
        "LM":  [{"x": 12, "y": 40}],
        "ST":  [{"x": 50, "y": 20}],
    },
    "4-4-2": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 74}],
        "CB":  [{"x": 36, "y": 74}, {"x": 64, "y": 74}],
        "LB":  [{"x": 12, "y": 74}],
        "RM":  [{"x": 88, "y": 50}],
        "CM":  [{"x": 36, "y": 50}, {"x": 64, "y": 50}],
        "LM":  [{"x": 12, "y": 50}],
        "ST":  [{"x": 36, "y": 21}, {"x": 64, "y": 21}],
    },
    "4-4-2 Diamond": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 74}],
        "CB":  [{"x": 36, "y": 74}, {"x": 64, "y": 74}],
        "LB":  [{"x": 12, "y": 74}],
        "CDM": [{"x": 50, "y": 60}],
        "CM":  [{"x": 28, "y": 46}, {"x": 72, "y": 46}],
        "CAM": [{"x": 50, "y": 33}],
        "ST":  [{"x": 36, "y": 19}, {"x": 64, "y": 19}],
    },
    "4-1-4-1": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 50, "y": 61}],
        "RM":  [{"x": 88, "y": 44}],
        "CM":  [{"x": 36, "y": 44}, {"x": 64, "y": 44}],
        "LM":  [{"x": 12, "y": 44}],
        "ST":  [{"x": 50, "y": 20}],
    },
    "3-5-2": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 74}, {"x": 50, "y": 74}, {"x": 75, "y": 74}],
        "LWB": [{"x": 11, "y": 55}],
        "CM":  [{"x": 30, "y": 48}, {"x": 50, "y": 48}, {"x": 70, "y": 48}],
        "RWB": [{"x": 89, "y": 55}],
        "ST":  [{"x": 36, "y": 21}, {"x": 64, "y": 21}],
    },
    "3-4-3": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "LWB": [{"x": 11, "y": 55}],
        "CM":  [{"x": 36, "y": 48}, {"x": 64, "y": 48}],
        "RWB": [{"x": 89, "y": 55}],
        "LW":  [{"x": 12, "y": 23}],
        "ST":  [{"x": 50, "y": 17}],
        "RW":  [{"x": 88, "y": 23}],
    },
    "5-3-2": {
        "GK":  [{"x": 50, "y": 91}],
        "LWB": [{"x": 11, "y": 74}],
        "CB":  [{"x": 28, "y": 78}, {"x": 50, "y": 78}, {"x": 72, "y": 78}],
        "RWB": [{"x": 89, "y": 74}],
        "CM":  [{"x": 25, "y": 51}, {"x": 50, "y": 51}, {"x": 75, "y": 51}],
        "ST":  [{"x": 36, "y": 21}, {"x": 64, "y": 21}],
    },
    # 4-4-1-1: flat mid four + CAM behind lone ST (the "number 10" role)
    "4-4-1-1": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "RM":  [{"x": 88, "y": 50}],
        "CM":  [{"x": 36, "y": 50}, {"x": 64, "y": 50}],
        "LM":  [{"x": 12, "y": 50}],
        "CAM": [{"x": 50, "y": 34}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 4-1-2-1-2: diamond (alias for 4-4-2 Diamond, used in API data)
    "4-1-2-1-2": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 74}],
        "CB":  [{"x": 36, "y": 74}, {"x": 64, "y": 74}],
        "LB":  [{"x": 12, "y": 74}],
        "CDM": [{"x": 50, "y": 60}],
        "CM":  [{"x": 28, "y": 46}, {"x": 72, "y": 46}],
        "CAM": [{"x": 50, "y": 33}],
        "ST":  [{"x": 36, "y": 19}, {"x": 64, "y": 19}],
    },
    # 4-1-3-2: single CDM shield + 3 attacking mids + 2 STs
    "4-1-3-2": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 50, "y": 63}],
        "CM":  [{"x": 22, "y": 46}, {"x": 50, "y": 46}, {"x": 78, "y": 46}],
        "ST":  [{"x": 36, "y": 20}, {"x": 64, "y": 20}],
    },
    # 4-2-2-2: double pivot + 2 CAMs + 2 STs ("magic box")
    "4-2-2-2": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 36, "y": 62}, {"x": 64, "y": 62}],
        "CAM": [{"x": 36, "y": 40}, {"x": 64, "y": 40}],
        "ST":  [{"x": 36, "y": 20}, {"x": 64, "y": 20}],
    },
    # 4-2-4: double pivot + 4 attackers (2 STs + 2 wide)
    "4-2-4": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 36, "y": 57}, {"x": 64, "y": 57}],
        "LW":  [{"x": 12, "y": 23}],
        "ST":  [{"x": 36, "y": 18}, {"x": 64, "y": 18}],
        "RW":  [{"x": 88, "y": 23}],
    },
    # 4-6-0: striker-less, 6 midfielders in 2 rows (2 CDM + 2 CM + 2 CAM)
    "4-6-0": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CDM": [{"x": 36, "y": 60}, {"x": 64, "y": 60}],
        "CM":  [{"x": 36, "y": 46}, {"x": 64, "y": 46}],
        "CAM": [{"x": 36, "y": 30}, {"x": 64, "y": 30}],
    },
    # 4-5-1: flat five-man midfield (RM, CM, CM, CM, LM) + lone striker
    "4-5-1": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "RM":  [{"x": 88, "y": 50}],
        "CM":  [{"x": 36, "y": 50}, {"x": 50, "y": 50}, {"x": 64, "y": 50}],
        "LM":  [{"x": 12, "y": 50}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 4-3-2-1: "Christmas Tree" — 3 CMs, 2 CAMs funnelling into 1 ST
    "4-3-2-1": {
        "GK":  [{"x": 50, "y": 91}],
        "RB":  [{"x": 88, "y": 75}],
        "CB":  [{"x": 36, "y": 75}, {"x": 64, "y": 75}],
        "LB":  [{"x": 12, "y": 75}],
        "CM":  [{"x": 25, "y": 57}, {"x": 50, "y": 57}, {"x": 75, "y": 57}],
        "CAM": [{"x": 35, "y": 38}, {"x": 65, "y": 38}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 3-4-1-2: 3 CBs, 2 WBs + 2 CMs, 1 CAM, 2 STs
    "3-4-1-2": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "LWB": [{"x": 11, "y": 60}],
        "CM":  [{"x": 36, "y": 53}, {"x": 64, "y": 53}],
        "RWB": [{"x": 89, "y": 60}],
        "CAM": [{"x": 50, "y": 37}],
        "ST":  [{"x": 36, "y": 20}, {"x": 64, "y": 20}],
    },
    # 3-2-4-1: 3 CBs, double pivot, wide 4-man mid, 1 ST
    "3-2-4-1": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "CDM": [{"x": 36, "y": 62}, {"x": 64, "y": 62}],
        "RM":  [{"x": 88, "y": 44}],
        "CM":  [{"x": 36, "y": 44}, {"x": 64, "y": 44}],
        "LM":  [{"x": 12, "y": 44}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 3-1-3-3: 3 CBs, 1 CDM, 3 CMs, 3 forwards
    "3-1-3-3": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "CDM": [{"x": 50, "y": 63}],
        "CM":  [{"x": 22, "y": 49}, {"x": 50, "y": 49}, {"x": 78, "y": 49}],
        "LW":  [{"x": 12, "y": 23}],
        "ST":  [{"x": 50, "y": 18}],
        "RW":  [{"x": 88, "y": 23}],
    },
    # 5-2-2-1: 5 defenders (3 CB + 2 WB), double pivot, 2 CAMs, 1 ST
    "5-2-2-1": {
        "GK":  [{"x": 50, "y": 91}],
        "LWB": [{"x": 11, "y": 74}],
        "CB":  [{"x": 28, "y": 78}, {"x": 50, "y": 78}, {"x": 72, "y": 78}],
        "RWB": [{"x": 89, "y": 74}],
        "CDM": [{"x": 36, "y": 57}, {"x": 64, "y": 57}],
        "CAM": [{"x": 36, "y": 38}, {"x": 64, "y": 38}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 5-4-1: 5 defenders, flat 4 mids, lone ST — ultra-defensive
    "5-4-1": {
        "GK":  [{"x": 50, "y": 91}],
        "LWB": [{"x": 11, "y": 74}],
        "CB":  [{"x": 28, "y": 78}, {"x": 50, "y": 78}, {"x": 72, "y": 78}],
        "RWB": [{"x": 89, "y": 74}],
        "RM":  [{"x": 88, "y": 50}],
        "CM":  [{"x": 36, "y": 50}, {"x": 64, "y": 50}],
        "LM":  [{"x": 12, "y": 50}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 3-5-1-1: 3 CBs, 5 mids (WBs + CMs), 1 CAM, 1 ST
    "3-5-1-1": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "LWB": [{"x": 11, "y": 57}],
        "CM":  [{"x": 25, "y": 50}, {"x": 50, "y": 50}, {"x": 75, "y": 50}],
        "RWB": [{"x": 89, "y": 57}],
        "CAM": [{"x": 50, "y": 33}],
        "ST":  [{"x": 50, "y": 20}],
    },
    # 3-4-2-1: three CBs, two WBs, two CMs, two CAMs, one ST
    "3-4-2-1": {
        "GK":  [{"x": 50, "y": 91}],
        "CB":  [{"x": 25, "y": 75}, {"x": 50, "y": 75}, {"x": 75, "y": 75}],
        "LWB": [{"x": 11, "y": 60}],
        "CM":  [{"x": 36, "y": 48}, {"x": 64, "y": 48}],
        "RWB": [{"x": 89, "y": 60}],
        "CAM": [{"x": 35, "y": 30}, {"x": 65, "y": 30}],
        "ST":  [{"x": 50, "y": 18}],
    },
}

# Line groupings for drawing connector lines
POSITION_LINES = [
    {"name": "gk",       "positions": {"GK"}},
    {"name": "defense",  "positions": {"RB", "CB", "LB", "RWB", "LWB"}},
    {"name": "def_mid",  "positions": {"CDM"}},
    {"name": "mid",      "positions": {"CM", "CAM", "RM", "LM"}},
    {"name": "attack",   "positions": {"RW", "LW", "ST", "CF"}},
]


def _get_coords(formation: str, slot: str, slot_index: int) -> dict:
    """Return x, y percentage coords for a given slot and its occurrence index."""
    coords_map = FORMATION_COORDS.get(formation, FORMATION_COORDS["4-3-3"])
    positions = coords_map.get(slot, [])
    if not positions:
        # Fallback: center of the pitch
        return {"x": 50, "y": 50}
    idx = min(slot_index, len(positions) - 1)
    return positions[idx]


def _shorten_name(name: str) -> str:
    """Shorten player name for display: 'M. Salah', 'Haaland', etc."""
    parts = name.split()
    if len(parts) == 1:
        return name
    # For long names, show first initial + last name
    if len(name) > 14:
        return f"{parts[0][0]}. {parts[-1]}"
    return name


def _initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0].upper() for p in parts[:2])


def _build_player_data(totw: TOTWSelection) -> list[dict]:
    """Build the player data list for the Jinja2 template."""
    players_data = []
    slot_counts: dict[str, int] = {}

    for tp in totw.players:
        slot = tp.position_slot
        idx = slot_counts.get(slot, 0)
        slot_counts[slot] = idx + 1

        coords = _get_coords(totw.formation.formation, slot, idx)
        p = tp.player

        players_data.append({
            "name": p.name,
            "display_name": _shorten_name(p.name),
            "initials": _initials(p.name),
            "position_slot": slot,
            "photo_url": p.photo_url,
            "team_badge_url": p.team_badge_url,
            "flag_url": p.flag_url,
            "nationality": p.nationality,
            "team_name": p.team_name,
            "rating": p.stats.games.rating or "",
            "x": coords["x"],
            "y": coords["y"],
        })

    return players_data


def _build_connector_lines(
    players_data: list[dict],
    formation: str,
) -> list[dict]:
    """Build connector line data between players in the same line group."""
    # Map position slot → pixel coords (using percentages * dimensions)
    W, H = 900, 1260
    pos_coords: dict[str, list[tuple[float, float]]] = {}

    for p in players_data:
        slot = p["position_slot"]
        px = (p["x"] / 100) * W
        py = (p["y"] / 100) * H
        pos_coords.setdefault(slot, []).append((px, py))

    lines = []
    for line_group in POSITION_LINES:
        group_positions = line_group["positions"]
        # Collect all player positions in this line group, sorted by x
        group_coords: list[tuple[float, float]] = []
        for slot, coords in pos_coords.items():
            if slot in group_positions:
                group_coords.extend(coords)

        if len(group_coords) < 2:
            continue

        # Sort by x coordinate and draw lines between adjacent players
        group_coords.sort(key=lambda c: c[0])
        for i in range(len(group_coords) - 1):
            x1, y1 = group_coords[i]
            x2, y2 = group_coords[i + 1]
            lines.append({"x1": round(x1), "y1": round(y1), "x2": round(x2), "y2": round(y2)})

    return lines


def render_html(totw: TOTWSelection) -> str:
    """Render the pitch.html Jinja2 template with player data."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("pitch.html")

    players_data = _build_player_data(totw)
    connector_lines = _build_connector_lines(players_data, totw.formation.formation)

    return template.render(
        matchweek=totw.matchweek,
        formation=totw.formation.formation,
        players=players_data,
        connector_lines=connector_lines,
    )


async def _screenshot_html(html: str, output_path: Path) -> None:
    """Render HTML string to PNG via Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 900, "height": 1330}, device_scale_factor=2)

        await page.set_content(html, wait_until="networkidle")

        # Wait for images to load
        await page.wait_for_timeout(3000)

        await page.screenshot(
            path=str(output_path),
            full_page=False,
            clip={"x": 0, "y": 0, "width": 900, "height": 1330},
        )
        await browser.close()


def render_diagram(matchweek: int) -> Path:
    """Full pipeline: load TOTW → render HTML → screenshot PNG."""
    # Load TOTW selection
    analysis_dir = matchweek_analysis_dir(matchweek)
    players_path = analysis_dir / "players.json"
    data = load_json_cache(players_path)
    if not data:
        raise FileNotFoundError(
            f"No players.json for matchweek {matchweek}. "
            f"Run player_evaluator.py first."
        )
    totw = TOTWSelection(**data)

    print(f"Rendering diagram for matchweek {matchweek}...")
    print(f"  Formation: {totw.formation.formation}")
    print(f"  Players: {len(totw.players)}")

    # Render HTML
    html = render_html(totw)

    # Save HTML for debugging
    html_path = matchweek_output_dir(matchweek) / "totw_diagram.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  HTML saved: {html_path}")

    # Screenshot
    png_path = matchweek_output_dir(matchweek) / "totw_diagram.png"
    asyncio.run(_screenshot_html(html, png_path))
    print(f"  PNG saved: {png_path}")

    size_kb = png_path.stat().st_size // 1024
    print(f"  File size: {size_kb} KB")

    return png_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagram_renderer.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    output_path = render_diagram(matchweek)
    print(f"\nDone. Open: {output_path}")


if __name__ == "__main__":
    main()
