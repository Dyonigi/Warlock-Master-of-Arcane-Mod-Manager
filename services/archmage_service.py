"""Lettura/scrittura di fractions.binary.xml per l'editor di Archmages e Improvements.
Nessun tkinter. Stesso schema di perk_service: ogni operazione rilegge il file, modifica e riscrive
con le funzioni dell'editor XML del manager."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import archmage_schema as am
from services.perk_service import parse_xml_file, write_xml_file

FRACTIONS_KEY = "fractions.binary"


@dataclass
class FractionsInfo:
    archmages: List[am.Archmage] = field(default_factory=list)
    improvements: List[am.Improvement] = field(default_factory=list)

    @property
    def races(self) -> List[str]:
        return _uniq(a.race for a in self.archmages)

    @property
    def colors(self) -> List[int]:
        return sorted({a.selected_color for a in self.archmages})

    @property
    def improvement_names(self) -> List[str]:
        return [i.name for i in self.improvements]

    @property
    def spells_seen(self) -> List[str]:
        return sorted({s for i in self.improvements for s in i.spells})


def _uniq(items) -> List[str]:
    out: List[str] = []
    for x in items:
        if x and x not in out:
            out.append(x)
    return out


def fractions_path(manifest: Dict[str, str]) -> Optional[str]:
    for orig, path in manifest.items():
        if orig.lower() == FRACTIONS_KEY:
            return path
    return None


def _load(path: str) -> Tuple[object, ET.Element]:
    tree = parse_xml_file(path)
    return tree, (tree.getroot() if hasattr(tree, "getroot") else tree)


def read_info(path: str) -> FractionsInfo:
    _tree, root = _load(path)
    return FractionsInfo(am.read_archmages(root), am.read_improvements(root))


def add_archmage(path: str, a: am.Archmage) -> int:
    tree, root = _load(path)
    names = {i.name for i in am.read_improvements(root)}
    pos = am.append_fraction(root, a.to_element(names))
    write_xml_file(tree, path)
    return pos


def update_archmage(path: str, a: am.Archmage) -> int:
    tree, root = _load(path)
    names = {i.name for i in am.read_improvements(root)}
    pos = am.replace_fraction(root, a.system_name, a.to_element(names))
    write_xml_file(tree, path)
    return pos


def add_improvement(path: str, imp: am.Improvement) -> int:
    tree, root = _load(path)
    pos = am.append_improvement(root, imp.to_element())
    write_xml_file(tree, path)
    return pos


def update_improvement(path: str, imp: am.Improvement) -> int:
    tree, root = _load(path)
    pos = am.replace_improvement(root, imp.name, imp.to_element())
    write_xml_file(tree, path)
    return pos
