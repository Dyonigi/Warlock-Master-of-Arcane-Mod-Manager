#!/usr/bin/env python3
"""Locate a Warlock: Master of the Arcane installation."""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional


GAME_FOLDER_NAME = "Warlock - Master of the Arcane"
GAME_EXE_NAMES = ("Game.exe", "Warlock.exe")
STEAM_APP_HINT = "Warlock - Master of the Arcane"

DEFAULT_HINTS = [
    r"C:\Applicazioni\Giochi\Steam\Steam\steamapps\common\Warlock - Master of the Arcane",
    r"C:\Program Files (x86)\Steam\steamapps\common\Warlock - Master of the Arcane",
    r"C:\Program Files\Steam\steamapps\common\Warlock - Master of the Arcane",
    r"D:\Steam\steamapps\common\Warlock - Master of the Arcane",
    r"E:\Steam\steamapps\common\Warlock - Master of the Arcane",
]


def is_game_dir(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    has_exe = any(os.path.isfile(os.path.join(path, name)) for name in GAME_EXE_NAMES)
    has_pack = any(
        name.endswith(".pack") and os.path.isfile(os.path.join(path, name))
        for name in os.listdir(path)
    )
    return has_exe and has_pack


def _steam_install_paths() -> List[str]:
    paths: List[str] = []
    try:
        import winreg  # type: ignore

        for hive, sub in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
        ):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "InstallPath")
                    if val:
                        paths.append(val)
            except OSError:
                continue
    except ImportError:
        pass
    for env in ("STEAM_PATH", "STEAM_DIR"):
        if os.environ.get(env):
            paths.append(os.environ[env])
    for candidate in (
        r"C:\Applicazioni\Giochi\Steam\Steam",
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
        os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
        os.path.expandvars(r"%ProgramFiles%\Steam"),
    ):
        if candidate:
            paths.append(candidate)
    uniq: List[str] = []
    seen = set()
    for p in paths:
        n = os.path.normpath(p)
        if n.lower() not in seen and os.path.isdir(n):
            seen.add(n.lower())
            uniq.append(n)
    return uniq


def _parse_library_folders(vdf_path: str) -> List[str]:
    if not os.path.isfile(vdf_path):
        return []
    try:
        text = open(vdf_path, "r", encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    libs = []
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        libs.append(m.group(1).replace("\\\\", "\\"))
    # older format: "0" "D:\\Steam"
    for m in re.finditer(r'"\d+"\s+"([A-Za-z]:[^"]+)"', text):
        libs.append(m.group(1).replace("\\\\", "\\"))
    return libs


def _iter_steam_libraries() -> Iterable[str]:
    for steam in _steam_install_paths():
        yield steam
        for rel in ("steamapps\\libraryfolders.vdf", "config\\libraryfolders.vdf"):
            for lib in _parse_library_folders(os.path.join(steam, rel)):
                yield lib


def find_game_dir(explicit: Optional[str] = None) -> Optional[str]:
    candidates: List[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(DEFAULT_HINTS)
    for lib in _iter_steam_libraries():
        candidates.append(os.path.join(lib, "steamapps", "common", GAME_FOLDER_NAME))
        candidates.append(os.path.join(lib, "SteamApps", "common", GAME_FOLDER_NAME))
        # already a steamapps/common parent?
        candidates.append(os.path.join(lib, "common", GAME_FOLDER_NAME))
    # walk up from this package (mods/warlock_mod_manager -> game root)
    here = os.path.abspath(os.path.dirname(__file__))
    candidates.append(os.path.dirname(os.path.dirname(here)))
    seen = set()
    for path in candidates:
        n = os.path.normpath(path)
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        if is_game_dir(n):
            return n
    return None
