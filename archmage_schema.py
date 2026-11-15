"""Modello degli Archmages (FractionData) e degli Improvements di fractions.binary.xml.
Nessuna dipendenza da tkinter.

Struttura (verificata su tutti i 19 FractionData e i 36 Improvement del gioco):

  <Fractions>
    <Fractions>   <FractionData> predefined, dlcId, frTemplate[version](systemName,
                  UserData[version](characterIcon, race, selectedColor,
                  characterName(key, national, cp), improvements(Item...))), personality(...)
    <Improvements> <Improvement> name, cost, gold, mana, perk, unitName, resourceName,
                  dlcId, dlc, Relation(godName, relationDelta), Spells(Item...)
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from perk_schema import NAME_RE, PerkError, _leaf, indent_item, normalize_value


class ArchmageError(PerkError):
    """Dati non validi o modifica non applicabile (stessa famiglia degli errori dei perk)."""


PERSONALITY_DEFAULT: List[Tuple[str, str, str]] = [
    ("cooperativenessTurns", "integer", "0"),
    ("treacheryTurns", "integer", "0"),
    ("greediness", "float", "1.0"),
    ("braveness", "float", "1.0"),
    ("evilness", "integer", "0"),
]
FRACTION_TAGS = ("predefined", "dlcId", "frTemplate", "personality")
USERDATA_TAGS = ("characterIcon", "race", "selectedColor", "characterName", "improvements")
IMPROVEMENT_TAGS = ("name", "cost", "gold", "mana", "perk", "unitName", "resourceName",
                    "dlcId", "dlc", "Relation", "Spells")


def _v(el: Optional[ET.Element], path: str, default: str = "") -> str:
    if el is None:
        return default
    c = el.find(path)
    return default if c is None or c.get("value") is None else c.get("value")


def _int(text: str, label: str) -> int:
    try:
        return int(str(text).strip())
    except ValueError as exc:
        raise ArchmageError(f"{label} deve essere un numero intero.") from exc


# ---------------------------------------------------------------------------
# Archmage
# ---------------------------------------------------------------------------

@dataclass
class Archmage:
    system_name: str = ""
    race: str = "humans"
    character_icon: str = ""
    selected_color: int = 0
    name_key: str = ""                 # "#mage_<systemName>"
    national: str = ""
    cp: int = 1252
    improvements: List[str] = field(default_factory=list)
    predefined: bool = True
    dlc_id: int = 0
    personality: List[Tuple[str, str, str]] = field(default_factory=lambda: list(PERSONALITY_DEFAULT))
    fr_version: str = "2"
    ud_version: str = "5"

    @property
    def loc_name_key(self) -> str:
        return (self.name_key or "#mage_" + self.system_name).lstrip("#").upper()

    @property
    def loc_desc_key(self) -> str:
        return self.loc_name_key + "_DESC"

    @classmethod
    def from_element(cls, el: ET.Element) -> "Archmage":
        extra = [c.tag for c in el if c.tag not in FRACTION_TAGS]
        tpl = el.find("frTemplate")
        ud = tpl.find("UserData") if tpl is not None else None
        if tpl is None or ud is None:
            raise ArchmageError("FractionData senza frTemplate/UserData.")
        extra += [c.tag for c in ud if c.tag not in USERDATA_TAGS]
        if extra:
            raise ArchmageError(f"Campi non gestiti dal form: {', '.join(extra)}")
        pers = el.find("personality")
        return cls(
            system_name=_v(tpl, "systemName"), race=_v(ud, "race"), character_icon=_v(ud, "characterIcon"),
            selected_color=_int(_v(ud, "selectedColor", "0"), "selectedColor"),
            name_key=_v(ud, "characterName/key"), national=_v(ud, "characterName/national"),
            cp=_int(_v(ud, "characterName/cp", "1252"), "cp"),
            improvements=[i.get("value") for i in (ud.find("improvements") if ud.find("improvements") is not None else [])],
            predefined=_v(el, "predefined", "0") == "1", dlc_id=_int(_v(el, "dlcId", "0"), "dlcId"),
            personality=[(c.tag, c.get("type") or "string", c.get("value") or "") for c in (pers if pers is not None else [])]
            or list(PERSONALITY_DEFAULT),
            fr_version=tpl.get("version") or "2", ud_version=ud.get("version") or "5",
        )

    def validate(self, improvement_names: Optional[set] = None) -> None:
        if not NAME_RE.match(self.system_name or ""):
            raise ArchmageError("systemName può contenere solo lettere, cifre e '_' (e non può essere vuoto).")
        if not self.race.strip():
            raise ArchmageError("Indica la razza (race).")
        if not self.character_icon.strip():
            raise ArchmageError("Indica l'immagine del ritratto (characterIcon).")
        if not self.name_key.strip():
            raise ArchmageError("Manca la chiave del nome.")
        if self.selected_color < 0:
            raise ArchmageError("selectedColor non può essere negativo.")
        if len(set(self.improvements)) != len(self.improvements):
            raise ArchmageError("La lista degli improvements contiene doppioni.")
        if improvement_names is not None:
            missing = [i for i in self.improvements if i not in improvement_names]
            if missing:
                raise ArchmageError(f"Improvements inesistenti: {', '.join(missing)}")
        for tag, typ, val in self.personality:
            normalize_value(typ, val)

    def to_element(self, improvement_names: Optional[set] = None) -> ET.Element:
        self.validate(improvement_names)
        fd = ET.Element("FractionData")
        fd.append(_leaf("predefined", "bool", "1" if self.predefined else "0"))
        fd.append(_leaf("dlcId", "integer", str(int(self.dlc_id))))
        tpl = ET.SubElement(fd, "frTemplate")
        tpl.set("version", self.fr_version)
        tpl.append(_leaf("systemName", "string", self.system_name))
        ud = ET.SubElement(tpl, "UserData")
        ud.set("version", self.ud_version)
        ud.append(_leaf("characterIcon", "string", self.character_icon))
        ud.append(_leaf("race", "string", self.race))
        ud.append(_leaf("selectedColor", "integer", str(int(self.selected_color))))
        cn = ET.SubElement(ud, "characterName")
        cn.append(_leaf("key", "string", self.name_key))
        cn.append(_leaf("national", "string", self.national))
        cn.append(_leaf("cp", "integer", str(int(self.cp))))
        imps = ET.SubElement(ud, "improvements")
        for i in self.improvements:
            imps.append(_leaf("Item", "string", i))
        pers = ET.SubElement(fd, "personality")
        for tag, typ, val in self.personality:
            pers.append(_leaf(tag, typ, normalize_value(typ, val)))
        indent_item(fd, 2)
        return fd


# ---------------------------------------------------------------------------
# Improvement
# ---------------------------------------------------------------------------

@dataclass
class Improvement:
    name: str = ""
    cost: int = 1
    gold: int = 0
    mana: int = 0
    perk: str = ""
    unit_name: str = ""
    resource_name: str = ""
    dlc_id: int = 0
    dlc: str = ""
    god_name: str = ""
    relation_delta: int = 0
    spells: List[str] = field(default_factory=list)

    @classmethod
    def from_element(cls, el: ET.Element) -> "Improvement":
        extra = [c.tag for c in el if c.tag not in IMPROVEMENT_TAGS]
        if extra:
            raise ArchmageError(f"Campi non gestiti dal form: {', '.join(extra)}")
        rel, sp = el.find("Relation"), el.find("Spells")
        return cls(
            name=_v(el, "name"), cost=_int(_v(el, "cost", "0"), "cost"), gold=_int(_v(el, "gold", "0"), "gold"),
            mana=_int(_v(el, "mana", "0"), "mana"), perk=_v(el, "perk"), unit_name=_v(el, "unitName"),
            resource_name=_v(el, "resourceName"), dlc_id=_int(_v(el, "dlcId", "0"), "dlcId"), dlc=_v(el, "dlc"),
            god_name=_v(rel, "godName"), relation_delta=_int(_v(rel, "relationDelta", "0"), "relationDelta"),
            spells=[i.get("value") for i in (sp if sp is not None else [])],
        )

    def validate(self) -> None:
        if not NAME_RE.match(self.name or ""):
            raise ArchmageError("Il nome può contenere solo lettere, cifre e '_' (e non può essere vuoto).")
        if self.cost < 0:
            raise ArchmageError("Il costo non può essere negativo.")
        if len(set(self.spells)) != len(self.spells):
            raise ArchmageError("La lista degli incantesimi contiene doppioni.")

    def to_element(self) -> ET.Element:
        self.validate()
        it = ET.Element("Improvement")
        it.append(_leaf("name", "string", self.name))
        it.append(_leaf("cost", "integer", str(int(self.cost))))
        it.append(_leaf("gold", "integer", str(int(self.gold))))
        it.append(_leaf("mana", "integer", str(int(self.mana))))
        it.append(_leaf("perk", "string", self.perk))
        it.append(_leaf("unitName", "string", self.unit_name))
        it.append(_leaf("resourceName", "string", self.resource_name))
        it.append(_leaf("dlcId", "integer", str(int(self.dlc_id))))
        it.append(_leaf("dlc", "string", self.dlc))
        rel = ET.SubElement(it, "Relation")
        rel.append(_leaf("godName", "string", self.god_name))
        rel.append(_leaf("relationDelta", "integer", str(int(self.relation_delta))))
        sp = ET.SubElement(it, "Spells")
        for s in self.spells:
            sp.append(_leaf("Item", "string", s))
        indent_item(it, 2)
        return it


# ---------------------------------------------------------------------------
# Operazioni sul file
# ---------------------------------------------------------------------------

def fractions_section(root: ET.Element) -> ET.Element:
    sec = root.find("Fractions")
    if sec is None:
        raise ArchmageError("Sezione <Fractions> non trovata in fractions.binary.xml.")
    return sec


def improvements_section(root: ET.Element) -> ET.Element:
    sec = root.find("Improvements")
    if sec is None:
        raise ArchmageError("Sezione <Improvements> non trovata in fractions.binary.xml.")
    return sec


def read_archmages(root: ET.Element) -> List[Archmage]:
    return [Archmage.from_element(f) for f in fractions_section(root).findall("FractionData")]


def read_improvements(root: ET.Element) -> List[Improvement]:
    return [Improvement.from_element(i) for i in improvements_section(root).findall("Improvement")]


def _fix_tails(sec: ET.Element) -> None:
    items = list(sec)
    if not items:
        return
    mid = items[0].tail if len(items) > 1 and items[0].tail else "\n    "
    for it in items[:-1]:
        it.tail = mid
    items[-1].tail = "\n  "


def _find(sec: ET.Element, tag: str, path: str, name: str) -> Optional[Tuple[int, ET.Element]]:
    for i, el in enumerate(list(sec)):
        if el.tag == tag and _v(el, path) == name:
            return i, el
    return None


def append_fraction(root: ET.Element, el: ET.Element) -> int:
    """Aggiunge l'archmage IN CODA (l'ordine del file non è alfabetico e non so se il gioco usi la
    posizione, quindi gli archmage esistenti non si spostano)."""
    sec = fractions_section(root)
    name = _v(el, "frTemplate/systemName")
    if _find(sec, "FractionData", "frTemplate/systemName", name):
        raise ArchmageError(f"Esiste già un archmage con systemName '{name}'.")
    last = max((i for i, c in enumerate(sec) if c.tag == "FractionData"), default=len(sec) - 1)
    sec.insert(last + 1, el)
    _fix_tails(sec)
    return last + 1


def replace_fraction(root: ET.Element, system_name: str, el: ET.Element) -> int:
    sec = fractions_section(root)
    found = _find(sec, "FractionData", "frTemplate/systemName", system_name)
    if found is None:
        raise ArchmageError(f"Archmage '{system_name}' non trovato.")
    if _v(el, "frTemplate/systemName") != system_name:
        raise ArchmageError("systemName non si può cambiare in modifica: usa 'Duplica'.")
    idx, old = found
    sec.remove(old)
    sec.insert(idx, el)
    _fix_tails(sec)
    return idx


def append_improvement(root: ET.Element, el: ET.Element) -> int:
    sec = improvements_section(root)
    name = _v(el, "name")
    if _find(sec, "Improvement", "name", name):
        raise ArchmageError(f"Esiste già un improvement chiamato '{name}'.")
    sec.append(el)
    _fix_tails(sec)
    return len(sec) - 1


def replace_improvement(root: ET.Element, name: str, el: ET.Element) -> int:
    sec = improvements_section(root)
    found = _find(sec, "Improvement", "name", name)
    if found is None:
        raise ArchmageError(f"Improvement '{name}' non trovato.")
    if _v(el, "name") != name:
        raise ArchmageError("Il nome non si può cambiare in modifica: usa 'Duplica'.")
    idx, old = found
    sec.remove(old)
    sec.insert(idx, el)
    _fix_tails(sec)
    return idx


def improvement_users(root: ET.Element, name: str) -> List[str]:
    """systemName degli archmage che hanno questo improvement."""
    return [a.system_name for a in read_archmages(root) if name in a.improvements]
