#!/usr/bin/env python3
"""Map packed filenames to editable game-aspect categories."""

from __future__ import annotations

from typing import Dict, List, Tuple


# Vanilla packs that ship with the game / DLC markers — not user mods.
VANILLA_PACKS = {
    "d100.pack",
    "d110.pack",
    "d120.pack",
    "l100.pack",
    "m00.pack",
    "m01.pack",
    "m02.pack",
    "m03.pack",
    "m04.pack",
    "s100.pack",
}

# Later prefix groups override earlier ones; within a group, higher numbers win.
PACK_PREFIX_ORDER = ("s", "l", "m", "d")

EDITABLE_EXTENSIONS = {".binary", ".lua", ".xml", ".hgp", ".ini"}

CATEGORIES: List[Tuple[str, str, List[str]]] = [
    (
        "units",
        "Units",
        ["units.binary", "unitlevelups.binary", "unitavatars.binary", "formations.binary"],
    ),
    (
        "combat",
        "Combat & actions",
        ["actionviewdatalist.binary", "spelleffectsdatalist.binary"],
    ),
    (
        "spells",
        "Spells",
        ["spells.binary"],
    ),
    (
        "perks",
        "Perks & abilities",
        ["perks.binary", "perksviewdatalist.binary"],
    ),
    (
        "buildings",
        "Buildings",
        ["buildings.binary", "buildingtrees.binary", "buildingsview.binary"],
    ),
    (
        "factions",
        "Factions, races & gods",
        ["fractions.binary", "races.binary", "gods.binary"],
    ),
    (
        "quests",
        "Quests & events",
        ["quests.binary", "asks.binary", "randomeventdatalist.binary"],
    ),
    (
        "world",
        "World, tiles & resources",
        [
            "localresources.binary",
            "tiledefs.binary",
            "tileinfolist.binary",
            "landtypedata.binary",
            "environment.binary",
            "structuredatalist.binary",
            "genlimits.binary",
        ],
    ),
    (
        "ai",
        "AI & difficulty",
        ["ai.binary", "difflevels.binary", "logicparams.binary"],
    ),
    (
        "artifacts",
        "Artifacts",
        ["artifactdatalist.binary"],
    ),
    (
        "audio",
        "Sounds",
        [
            "unitbattlesounds.binary",
            "unitmovesounds.binary",
            "idlesounds.binary",
            "landscapesounds.binary",
            "dialogsounds.binary",
        ],
    ),
    (
        "graphics_defs",
        "Graphics definitions",
        ["gfxdefs.binary", "skydataex.binary", "renderparams.binary", "videoquality.binary"],
    ),
    (
        "ui_input",
        "UI & input",
        ["inputactions.binary"],
    ),
    (
        "scripts",
        "Lua scripts",
        [
            "battle.lua",
            "generator.lua",
            "ai.lua",
            "system.lua",
            "utils.lua",
            "combos.lua",
            "checkglobals.lua",
            "scriptlist.xml",
        ],
    ),
    (
        "misc",
        "Other data",
        ["armypresetdatalist.binary", "treedatalist.binary", "sfxattach.binary", "tbm.ini"],
    ),
]

FILE_TO_CATEGORY: Dict[str, Tuple[str, str]] = {}
for cat_id, label, files in CATEGORIES:
    for fname in files:
        FILE_TO_CATEGORY[fname.lower()] = (cat_id, label)


def category_for(filename: str) -> Tuple[str, str]:
    key = filename.lower()
    if key in FILE_TO_CATEGORY:
        return FILE_TO_CATEGORY[key]
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext == ".lua":
        return "scripts", "Lua scripts"
    if ext in {".dds", ".jpg", ".jpeg", ".tga", ".gfx", ".fnt", ".cur"}:
        return "assets", "Images & UI assets"
    if ext in {".bms", ".bma", ".bca", ".bsa", ".rdl"}:
        return "models", "3D models"
    if ext in {".ogg", ".ogm", ".fsb", ".fev"}:
        return "audio_files", "Audio files"
    if ext == ".hgp":
        return "world", "World, tiles & resources"
    if ext == ".binary":
        return "misc", "Other data"
    return "other", "Other files"


def is_editable_data_file(filename: str) -> bool:
    lower = filename.lower()
    if lower.endswith(".binary"):
        return True
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    return ext in EDITABLE_EXTENSIONS


def pack_sort_key(filename: str) -> Tuple[int, int, str]:
    name = os_basename(filename).lower()
    stem, _, ext = name.partition(".")
    if ext != "pack" or len(stem) < 2:
        return (99, 0, name)
    prefix = stem[0]
    num_part = stem[1:]
    try:
        number = int(num_part)
    except ValueError:
        number = 0
    try:
        group = PACK_PREFIX_ORDER.index(prefix)
    except ValueError:
        group = 50
    return (group, number, name)


def os_basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def next_mod_pack_name(existing_pack_names: List[str], start_at: int = 130) -> str:
    highest = start_at - 1
    for name in existing_pack_names:
        stem = os_basename(name).lower()
        if stem.startswith("d") and stem.endswith(".pack"):
            num = stem[1:-5]
            if num.isdigit():
                highest = max(highest, int(num))
    return f"d{highest + 1:03d}.pack" if highest + 1 < 1000 else f"d{highest + 1}.pack"


def identity_fields() -> List[str]:
    return [
        "typeName",
        "name",
        "id",
        "spellName",
        "buildingName",
        "unitName",
        "perkName",
        "questName",
    ]
