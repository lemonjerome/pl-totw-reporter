"""
Merge Analyst Selections for the EPL TOTW Builder.

Reads analyst_1.json, analyst_2.json, analyst_3.json from the analysis output
directory, looks up each selected player from the raw SofaScore cache, and
writes the final players.json.

CLI:
    python scripts/merge_analyst_selections.py 30
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_models import (
    SelectedFormation,
    TOTWPlayer,
    TOTWSelection,
)
from scripts.player_evaluator import (
    _build_key_stat,
    _build_reason,
    _parse_player_from_cache,
    load_all_players,
    save_totw_selection,
)
from scripts.utils import (
    load_json_cache,
    matchweek_analysis_dir,
    matchweek_data_dir,
)


def _load_analyst_file(path: Path) -> list[dict]:
    """Load selections from an analyst JSON file. Returns [] if missing."""
    if not path.exists():
        print(f"  [WARN] Missing analyst file: {path}")
        return []
    data = json.loads(path.read_text())
    return data.get("selections", [])


def merge_analyst_selections(matchweek: int) -> TOTWSelection:
    """
    Merge analyst_1/2/3.json into a complete TOTWSelection.
    Falls back to shortlist rank-1 for any slot not covered by analysts.
    """
    analysis_dir = matchweek_analysis_dir(matchweek)

    # Load formation
    formation_data = load_json_cache(analysis_dir / "formation.json")
    if not formation_data:
        raise FileNotFoundError(f"formation.json not found for matchweek {matchweek}")
    formation = SelectedFormation(**formation_data)

    # Load shortlists as fallback
    shortlist_data = load_json_cache(analysis_dir / "shortlists.json") or {}
    shortlist_by_slot: dict[int, dict] = {}
    for slot in shortlist_data.get("slots", []):
        shortlist_by_slot[slot["slot_index"]] = slot

    # Load all 3 analyst outputs
    all_selections: list[dict] = []
    for analyst_id in (1, 2, 3):
        path = analysis_dir / f"analyst_{analyst_id}.json"
        selections = _load_analyst_file(path)
        all_selections.extend(selections)

    # Index by slot_index (last write wins if duplicate)
    selection_by_slot: dict[int, dict] = {}
    for sel in all_selections:
        selection_by_slot[sel["slot_index"]] = sel

    # Pre-load all players from cache for fast lookup
    print(f"  Loading players from cache for matchweek {matchweek}...")
    all_players = load_all_players(matchweek)
    player_by_id: dict[int, object] = {p.player_id: p for p in all_players}

    # Build TOTWPlayers in slot order
    totw_players: list[TOTWPlayer] = []
    positions = formation.positions

    for slot_idx, position_slot in enumerate(positions):
        sel = selection_by_slot.get(slot_idx)

        if sel:
            player_id = sel.get("player_id")
            player = player_by_id.get(player_id)

            if player is None:
                print(f"  [WARN] Player ID {player_id} not found in cache for slot {slot_idx} ({position_slot})")
                player = _fallback_player(slot_idx, shortlist_by_slot, player_by_id)

            if player:
                totw_players.append(TOTWPlayer(
                    position_slot=position_slot,
                    player=player,
                    selection_reason=sel.get("selection_reason") or _build_reason(player, position_slot),
                    key_stat=sel.get("key_stat") or _build_key_stat(player, position_slot),
                ))
                print(f"  ✅ [{slot_idx}] {position_slot}: {player.name} ({player.team_name})")
        else:
            # No analyst covered this slot — fall back to shortlist rank 1
            player = _fallback_player(slot_idx, shortlist_by_slot, player_by_id)
            if player:
                totw_players.append(TOTWPlayer(
                    position_slot=position_slot,
                    player=player,
                    selection_reason=_build_reason(player, position_slot),
                    key_stat=_build_key_stat(player, position_slot),
                ))
                print(f"  ⚠️  [{slot_idx}] {position_slot}: {player.name} ({player.team_name}) [fallback: rank 1]")
            else:
                print(f"  ❌ [{slot_idx}] {position_slot}: no candidate found — skipped")

    return TOTWSelection(matchweek=matchweek, formation=formation, players=totw_players)


def _fallback_player(
    slot_idx: int,
    shortlist_by_slot: dict[int, dict],
    player_by_id: dict[int, object],
) -> Optional[object]:
    """Return the rank-1 candidate from the shortlist for this slot."""
    slot = shortlist_by_slot.get(slot_idx)
    if not slot or not slot.get("candidates"):
        return None
    rank1 = slot["candidates"][0]
    return player_by_id.get(rank1["player_id"])


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/merge_analyst_selections.py <matchweek>")
        sys.exit(1)

    matchweek = int(sys.argv[1])
    print(f"\nMerging analyst selections for matchweek {matchweek}...")

    totw = merge_analyst_selections(matchweek)
    out_path = save_totw_selection(matchweek, totw)

    print(f"\nFinal TOTW — {len(totw.players)} players:")
    for tp in totw.players:
        print(f"  {tp.position_slot:<6} {tp.player.name:<28} {tp.player.team_name}")
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    main()
