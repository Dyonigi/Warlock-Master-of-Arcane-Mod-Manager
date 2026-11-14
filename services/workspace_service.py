"""Load a workspace from packs and build the cross-file reference index."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import shutil
from typing import Callable, Dict, Iterable, List, Optional

from packio import list_pack, unpack_pack
from project import (
    load_localization, 
    merged_entries, 
    write_workspace, 
    parse_locdata_to_text
)
from xmlmodel import build_definition_index


LogFn = Callable[[str], None]
Manifest = Dict[str, str]           # original packed name -> editable file path
RefIndex = Dict[str, Dict[str, ET.Element]]   # original filename -> {identity: node}


def load_workspace(
    pack_paths: Iterable[str],
    dest_dir: str,
    *,
    only_editable: bool = True,
    log: Optional[LogFn] = None,
) -> Manifest:
    """Merge the given packs into `dest_dir` and return the manifest."""
    path_list = list(pack_paths)
    
    merged = merged_entries(path_list, only_editable=only_editable, log=log)
    manifest = write_workspace(dest_dir, merged, convert_txml=True, log=log)

    # --- ESTRAZIONE LOCDATA ---
    # Cerchiamo il file l100.pack (o chiunque contenga locdata.md) nei pack caricati
    for pack_path in path_list:
        try:
            entries = list_pack(pack_path)
        except Exception:
            continue
            
        if any(e.name.lower() == "locdata.md" for e in entries):
            tmp_dir = os.path.join(dest_dir, "_tmp_loc")
            try:
                unpack_pack(pack_path, tmp_dir, names=["locdata.md"])
                src_path = os.path.join(tmp_dir, "locdata.md")
                
                if os.path.isfile(src_path):
                    # Convertiamo in formato leggibile
                    text = parse_locdata_to_text(src_path)
                    out_path = os.path.join(dest_dir, "locdata.loc")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    
                    # Lo aggiungiamo al manifest così appare nel browser
                    manifest["locdata.md"] = out_path
                    if log: 
                        log("Extracted locdata.md -> locdata.loc for editing.")
                
                shutil.rmtree(tmp_dir, ignore_errors=True)
                break # Trovato e processato, usciamo dal loop
            except Exception as e:
                if log: 
                    log(f"Error extracting locdata.md: {e}")
                shutil.rmtree(tmp_dir, ignore_errors=True)

    return manifest


def load_localization_from_pack(game_dir: str, workspace_dest: str, log: Optional[LogFn] = None) -> Dict[str, str]:
    """Extract locdata.md from l100.pack and return {UPPER_KEY: display}."""
    loc_pack = os.path.join(game_dir, "l100.pack")
    if not os.path.isfile(loc_pack):
        if log:
            log("l100.pack not found — display names unavailable.")
        return {}
    try:
        entries = list_pack(loc_pack)
    except Exception as exc:
        if log:
            log(f"Could not read l100.pack: {exc}")
        return {}
    if not any(e.name.lower() == "locdata.md" for e in entries):
        if log:
            log("locdata.md not found inside l100.pack.")
        return {}
    loc_dir = os.path.join(workspace_dest, "_loc")
    try:
        unpack_pack(loc_pack, loc_dir, names=["locdata.md"])
        loc_path = os.path.join(loc_dir, "locdata.md")
        names = load_localization(loc_path)
        if log:
            log(f"Localization loaded: {len(names)} entries.")
        return names
    except Exception as exc:
        if log:
            log(f"locdata.md not loaded: {exc}")
        return {}


def build_reference_index(manifest: Manifest, log: Optional[LogFn] = None) -> RefIndex:
    """Index every XML file in the manifest by identity for cross-file jumps."""
    index: RefIndex = {}
    for orig, path in manifest.items():
        if not path.lower().endswith(".xml"):
            continue
        try:
            tree = ET.parse(path)
        except Exception:
            continue
        idx = build_definition_index(tree.getroot())
        if idx:
            index[orig] = idx
    if log:
        log(f"Indexed {len(index)} file(s) for reference jumps.")
    return index