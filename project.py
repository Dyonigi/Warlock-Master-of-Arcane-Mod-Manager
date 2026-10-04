#!/usr/bin/env python3
"""Scan, merge, unpack, convert, pack and install Warlock mods."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from catalog import VANILLA_PACKS, is_editable_data_file, next_mod_pack_name, pack_sort_key
from packio import list_pack, pack_dir, read_entry
from txml import is_txml, txml_to_xml_string, xml_string_to_txml


LogFn = Callable[[str], None]


def _log(log: Optional[LogFn], msg: str) -> None:
    if log:
        log(msg)


def file_sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def bytes_sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


@dataclass
class PackInfo:
    path: str
    name: str
    size: int
    sha1: str
    files: List[str]
    vanilla: bool


@dataclass
class ModBundle:
    name: str
    path: str
    packs: List[str]
    notes: str = ""


@dataclass
class GameScan:
    game_dir: str
    all_packs: List[PackInfo]
    installed_mods: List[PackInfo]
    vanilla_packs: List[PackInfo]
    available_mods: List[ModBundle]


def list_game_packs(game_dir: str) -> List[PackInfo]:
    packs: List[PackInfo] = []
    for name in os.listdir(game_dir):
        if not name.lower().endswith(".pack"):
            continue
        path = os.path.join(game_dir, name)
        try:
            entries = list_pack(path)
            files = [e.name for e in entries]
        except Exception:
            files = []
        packs.append(
            PackInfo(
                path=path,
                name=name,
                size=os.path.getsize(path),
                sha1=file_sha1(path),
                files=files,
                vanilla=name.lower() in VANILLA_PACKS,
            )
        )
    packs.sort(key=lambda p: pack_sort_key(p.name))
    return packs


def _read_notes(folder: str) -> str:
    bits: List[str] = []
    for candidate in ("descript.ion", "README.txt", "readme.txt", "changelog.txt"):
        path = os.path.join(folder, candidate)
        if os.path.isfile(path):
            try:
                text = open(path, "r", encoding="utf-8", errors="ignore").read().strip()
            except OSError:
                continue
            if text:
                bits.append(text[:2000])
    for name in os.listdir(folder):
        if name.lower().startswith("changelog") and name.lower().endswith(".txt"):
            path = os.path.join(folder, name)
            try:
                bits.append(open(path, "r", encoding="utf-8", errors="ignore").read()[:4000])
            except OSError:
                pass
            break
    return "\n\n".join(bits)


def scan_available_mods(mods_root: str) -> List[ModBundle]:
    bundles: List[ModBundle] = []
    if not os.path.isdir(mods_root):
        return bundles
    skip = {"warlock_mod_manager", "work", "__pycache__"}
    for name in sorted(os.listdir(mods_root)):
        if name in skip or name.startswith("."):
            continue
        path = os.path.join(mods_root, name)
        if os.path.isdir(path):
            packs = [
                os.path.join(path, f)
                for f in sorted(os.listdir(path))
                if f.lower().endswith(".pack")
            ]
            if packs:
                bundles.append(ModBundle(name=name, path=path, packs=packs, notes=_read_notes(path)))
        elif name.lower().endswith(".pack"):
            bundles.append(ModBundle(name=name, path=path, packs=[path], notes=""))
    return bundles


def scan_game(game_dir: str, mods_root: str) -> GameScan:
    packs = list_game_packs(game_dir)
    return GameScan(
        game_dir=game_dir,
        all_packs=packs,
        installed_mods=[p for p in packs if not p.vanilla],
        vanilla_packs=[p for p in packs if p.vanilla],
        available_mods=scan_available_mods(mods_root),
    )


def merged_entries(
    pack_paths: Iterable[str],
    only_editable: bool = True,
    log: Optional[LogFn] = None,
) -> Dict[str, Tuple[str, bytes]]:
    """Later packs in pack_paths override earlier files with the same name."""
    merged: Dict[str, Tuple[str, bytes]] = {}
    ordered = sorted(pack_paths, key=lambda p: pack_sort_key(os.path.basename(p)))
    for pack_path in ordered:
        try:
            entries = list_pack(pack_path)
        except Exception as exc:
            _log(log, f"Could not read {pack_path}: {exc}")
            continue
        for entry in entries:
            if only_editable and not is_editable_data_file(entry.name):
                continue
            try:
                data = read_entry(pack_path, entry)
            except Exception as exc:
                _log(log, f"Skip {entry.name} from {os.path.basename(pack_path)}: {exc}")
                continue
            merged[entry.name] = (os.path.basename(pack_path), data)
        _log(log, f"Merged {os.path.basename(pack_path)} ({len(entries)} files)")
    return merged


def write_workspace(
    dest_dir: str,
    merged: Dict[str, Tuple[str, bytes]],
    convert_txml: bool = True,
    log: Optional[LogFn] = None,
) -> Dict[str, str]:
    """Write files into dest_dir. TXML binaries become <name>.xml for editing.

    Returns mapping of original packed name -> path of the file to edit.
    """
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    manifest: Dict[str, str] = {}
    for name, (_src, data) in sorted(merged.items()):
        if convert_txml and name.lower().endswith(".binary") and is_txml(data):
            xml_name = name + ".xml"
            xml_path = os.path.join(dest_dir, xml_name)
            try:
                xml_text = txml_to_xml_string(data)
            except Exception as exc:
                _log(log, f"TXML convert failed for {name}: {exc}; writing raw binary")
                out_path = os.path.join(dest_dir, name)
                with open(out_path, "wb") as f:
                    f.write(data)
                manifest[name] = out_path
                continue
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_text)
            manifest[name] = xml_path
            _log(log, f"Converted {name} -> {xml_name}")
        else:
            out_path = os.path.join(dest_dir, name)
            with open(out_path, "wb") as f:
                f.write(data)
            manifest[name] = out_path
            _log(log, f"Wrote {name}")
    meta = os.path.join(dest_dir, "_manifest.txt")
    with open(meta, "w", encoding="utf-8") as f:
        for orig, path in sorted(manifest.items()):
            f.write(f"{orig}\t{os.path.basename(path)}\n")
    return manifest


def build_pack_from_workspace(
    workspace_dir: str,
    pack_path: str,
    selected_original_names: Optional[Iterable[str]] = None,
    log: Optional[LogFn] = None,
) -> str:
    staging = os.path.join(os.path.dirname(workspace_dir), "_pack_staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    wanted = set(selected_original_names) if selected_original_names is not None else None
    for name in os.listdir(workspace_dir):
        if name.startswith("_"):
            continue
        path = os.path.join(workspace_dir, name)
        if not os.path.isfile(path):
            continue
        if name.endswith(".binary.xml"):
            original = name[: -len(".xml")]
            if wanted is not None and original not in wanted:
                continue
            xml_text = open(path, "r", encoding="utf-8").read()
            binary = xml_string_to_txml(xml_text)
            out = os.path.join(staging, original)
            with open(out, "wb") as f:
                f.write(binary)
            _log(log, f"Repacked TXML {original}")
        else:
            original = name
            if wanted is not None and original not in wanted:
                continue
            shutil.copy2(path, os.path.join(staging, original))
            _log(log, f"Copied {original}")

    pack_dir(staging, pack_path)
    shutil.rmtree(staging, ignore_errors=True)
    _log(log, f"Created {pack_path}")
    return pack_path


def install_packs(pack_paths: Iterable[str], game_dir: str, log: Optional[LogFn] = None) -> List[str]:
    installed = []
    for src in pack_paths:
        dest = os.path.join(game_dir, os.path.basename(src))
        shutil.copy2(src, dest)
        installed.append(dest)
        _log(log, f"Installed {os.path.basename(src)}")
    return installed


def uninstall_packs(pack_names: Iterable[str], game_dir: str, log: Optional[LogFn] = None) -> None:
    for name in pack_names:
        if name.lower() in VANILLA_PACKS:
            _log(log, f"Refusing to delete vanilla pack {name}")
            continue
        path = os.path.join(game_dir, name)
        if os.path.isfile(path):
            os.remove(path)
            _log(log, f"Removed {name}")


def suggest_pack_name(game_dir: str) -> str:
    names = [n for n in os.listdir(game_dir) if n.lower().endswith(".pack")]
    return next_mod_pack_name(names)
