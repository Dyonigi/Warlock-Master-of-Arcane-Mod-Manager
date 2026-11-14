"""Lettura/scrittura di perks.binary.xml per l'editor dei perk (nessun tkinter).

Ogni operazione rilegge il file, modifica l'albero e lo riscrive con le stesse funzioni
dell'editor XML del manager (xmlmodel), così il risultato passa dalla stessa conversione
in .binary di tutti gli altri file."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import perk_schema as ps

try:  # le stesse funzioni dell'editor XML del manager
    from xmlmodel import parse_xml_file, write_xml_file
except ImportError:  # fuori dal progetto (test)
    def parse_xml_file(path: str):
        return ET.parse(path)

    def write_xml_file(tree, path: str) -> None:
        tree.write(path, encoding="utf-8")

PERKS_KEY = "perks.binary"


def perks_path(manifest: Dict[str, str]) -> Optional[str]:
    for orig, path in manifest.items():
        if orig.lower() == PERKS_KEY:
            return path
    return None


def _load(path: str) -> Tuple[object, ET.Element]:
    tree = parse_xml_file(path)
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    return tree, ps.perk_data_of(root)


def read_info(path: str) -> Tuple[Dict[str, str], ps.Schema, int]:
    """({nome: perkType}, schema, n. di inversioni dell'ordine alfabetico)."""
    _tree, pd = _load(path)
    types: Dict[str, str] = {}
    for it in pd:
        n = ps.item_name(it)
        t = it.find("perkType")
        types[n] = t.get("value") if t is not None and t.get("value") is not None else ""
    return types, ps.build_schema(list(pd)), ps.inversions(ps.list_names(pd))


def get_perk(path: str, name: str) -> ps.Perk:
    _tree, pd = _load(path)
    found = ps.find_item(pd, name)
    if found is None:
        raise ps.PerkError(f"Perk '{name}' non trovato in {os.path.basename(path)}.")
    return ps.Perk.from_element(found[1])


def add_perk(path: str, perk: ps.Perk) -> int:
    """Aggiunge il perk in ordine alfabetico. Ritorna la posizione (0-based)."""
    tree, pd = _load(path)
    pos = ps.insert_sorted(pd, perk.to_element())
    write_xml_file(tree, path)
    return pos


def update_perk(path: str, perk: ps.Perk) -> int:
    tree, pd = _load(path)
    pos = ps.replace_item(pd, perk.name, perk.to_element())
    write_xml_file(tree, path)
    return pos


def sort_list(path: str) -> int:
    tree, pd = _load(path)
    moved = ps.sort_items(pd)
    if moved:
        write_xml_file(tree, path)
    return moved