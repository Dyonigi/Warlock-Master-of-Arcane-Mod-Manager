"""Scan, install, uninstall game packs and mod bundles."""

from __future__ import annotations

import os
from typing import Callable, List, Optional

from catalog import VANILLA_PACKS
from project import (
    GameScan,
    install_packs as _install_packs,
    scan_game,
    suggest_pack_name,
    uninstall_packs as _uninstall_packs,
)


LogFn = Callable[[str], None]


def rescan(game_dir: str, mods_root: str) -> GameScan:
    """Read every .pack in the game folder and every bundle in mods/."""
    return scan_game(game_dir, mods_root)


def install_bundle(bundle_packs: List[str], game_dir: str, log: Optional[LogFn] = None) -> int:
    _install_packs(bundle_packs, game_dir, log)
    return len(bundle_packs)


def uninstall(names: List[str], game_dir: str, log: Optional[LogFn] = None) -> List[str]:
    """Refuse vanilla packs and remove the rest. Returns the removed names."""
    safe = [n for n in names if n.lower() not in VANILLA_PACKS]
    _uninstall_packs(safe, game_dir, log)
    return safe


def skipped_vanilla(names: List[str]) -> List[str]:
    return [n for n in names if n.lower() in VANILLA_PACKS]


def next_output_pack_name(game_dir: str) -> str:
    return suggest_pack_name(game_dir)