"""Modello dei perk di perks.binary.xml: schema di Conditions/Effects, conversione da/a XML,
inserimento in ordine alfabetico. Nessuna dipendenza da tkinter.

Lo schema (tipi di effetto, campi, valori usati) viene ricavato dal file stesso e fuso con
uno schema di base incorporato, così anche un perks.binary quasi vuoto funziona.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET

NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
FIELD_TYPES = ("string", "integer", "float", "bool")
KNOWN_ITEM_TAGS = (
    "name", "perkType", "manaUpkeep", "isGood", "isEnchant", "isChangeMoveType",
    "dlcId", "dlcIdIdx", "Conditions", "Effects", "Terminators",
)


class PerkError(Exception):
    """Dati del perk non validi o modifica non applicabile."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class FieldSpec:
    path: str                      # "value", "attackType", "bonus/resType"...
    type: str = "string"           # string | integer | float | bool
    values: List[str] = field(default_factory=list)   # valori già visti (suggerimenti)


@dataclass
class EffectSpec:
    tag: str
    fields: List[FieldSpec] = field(default_factory=list)


@dataclass
class Schema:
    effects: Dict[str, EffectSpec] = field(default_factory=dict)
    perk_types: List[str] = field(default_factory=list)
    clients: List[str] = field(default_factory=list)
    default_client: Dict[str, str] = field(default_factory=dict)   # perkType -> client più usato

    def to_json(self) -> str:
        return json.dumps({
            "effects": {t: [[f.path, f.type, f.values] for f in e.fields] for t, e in self.effects.items()},
            "perk_types": self.perk_types, "clients": self.clients, "default_client": self.default_client,
        }, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Schema":
        d = json.loads(text)
        s = cls(perk_types=list(d["perk_types"]), clients=list(d["clients"]),
                default_client=dict(d["default_client"]))
        for tag, fields in d["effects"].items():
            s.effects[tag] = EffectSpec(tag, [FieldSpec(p, t, list(v)) for p, t, v in fields])
        return s


def _leaf_paths(el: ET.Element, prefix: str = "") -> List[Tuple[str, ET.Element]]:
    out: List[Tuple[str, ET.Element]] = []
    for ch in el:
        path = prefix + ch.tag
        if len(ch):
            out += _leaf_paths(ch, path + "/")
        else:
            out.append((path, ch))
    return out


def _is_value_leaf(el: ET.Element) -> bool:
    return el.get("type") is not None and el.get("value") is not None


def _add_values(spec: FieldSpec, vals: Iterable[str]) -> None:
    for v in vals:
        if v not in spec.values:
            spec.values.append(v)


def merge_items(schema: Schema, items: Iterable[ET.Element]) -> Schema:
    """Aggiunge allo schema ciò che si trova negli <item> dati (non toglie mai nulla)."""
    freq: Dict[Tuple[str, str], Counter] = {}
    ptypes: Counter = Counter()
    clients: Counter = Counter()
    by_type: Dict[str, Counter] = {}
    for it in items:
        pt = (it.find("perkType").get("value") if it.find("perkType") is not None else None)
        if pt:
            ptypes[pt] += 1
        for c in (it.find("Conditions") if it.find("Conditions") is not None else []):
            cl = c.find("client")
            if c.tag == "ClientConditionData" and cl is not None and cl.get("value"):
                clients[cl.get("value")] += 1
                if pt:
                    by_type.setdefault(pt, Counter())[cl.get("value")] += 1
        for e in (it.find("Effects") if it.find("Effects") is not None else []):
            if _is_value_leaf(e):          # elemento anomalo (es. <statusName value=.../>): solo XML grezzo
                continue
            spec = schema.effects.setdefault(e.tag, EffectSpec(e.tag))
            have = {f.path: f for f in spec.fields}
            for path, leaf in _leaf_paths(e):
                if not _is_value_leaf(leaf):
                    continue
                f = have.get(path)
                if f is None:
                    f = FieldSpec(path, leaf.get("type"))
                    spec.fields.append(f)
                    have[path] = f
                freq.setdefault((e.tag, path), Counter())[leaf.get("value")] += 1
    for (tag, path), cnt in freq.items():
        spec = next(f for f in schema.effects[tag].fields if f.path == path)
        if spec.type == "string":
            _add_values(spec, [v for v, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))])
    for v, _ in ptypes.most_common():
        if v not in schema.perk_types:
            schema.perk_types.append(v)
    for v, _ in clients.most_common():
        if v not in schema.clients:
            schema.clients.append(v)
    for pt, cnt in by_type.items():
        schema.default_client.setdefault(pt, cnt.most_common(1)[0][0])
    return schema


_BASE_SCHEMA_JSON = r'''{"clients": ["ownerUnit", "neighbourFriendUnit", "ownerTown", "ownerFraction", "fraction", "fractionUnit", "neighbourEnemyUnit"], "default_client": {"Artifact": "ownerUnit", "Fraction": "ownerFraction", "Race": "ownerTown", "Town": "ownerTown", "Unit": "ownerUnit"}, "effects": {"AddAction": [["actionName", "string", ["act_abr_agrelas_bless_high", "act_abr_dau_bless_high", "act_abr_far_shot", "act_abr_fireball", "act_abr_firestorm", "act_abr_gru_bless_high", "act_abr_heal", "act_abr_sunblast", "act_acid_explosion", "act_aoe_death", "act_armor_hartred", "act_black_mage_death_aoe", "act_black_mage_shadowball", "act_black_mage_summon", "act_brute_dot", "act_elf_armor_penetrate", "act_elf_lord_aoe_arrows", "act_elf_lord_aoe_roots", "act_elf_lord_magic_arrow", "act_fast_dot", "act_ghost_gift_of_darkness", "act_ghost_transformation", "act_goblin_bow_aoe_shot", "act_healer_sympathy", "act_hit_with_swoop", "act_knight_cleave", "act_lord_barlog_fire_wall", "act_lord_barlog_stone_hit", "act_lord_barlog_teleport", "act_lord_blademaster_bonesetter", "act_lord_blademaster_heavy_hit", "act_lord_blademaster_invincible", "act_lord_cleric_aoe_heal", "act_lord_cleric_breathe", "act_lord_cleric_no_cd", "act_lord_cleric_shield", "act_lord_goblin_acid_arrow", "act_lord_goblin_dark_arrow", "act_lord_goblin_paralyze", "act_lord_goblin_super_shot", "act_lord_imp_fire_ring", "act_lord_imp_fireball", "act_lord_imp_summon", "act_lord_imp_weak_healer", "act_lord_pala_ring_attack", "act_lord_pala_teleport", "act_lord_vamp_mind_blast", "act_lord_vamp_reconstruction", "act_lord_werewolf_alchemy", "act_lord_werewolf_elem_hit", "act_lord_wizard_fire_lasso", "act_lord_wizard_fire_launcher", "act_lord_wizard_fire_ring", "act_lorg_ogre_curveball", "act_lorg_ogre_sleepiness", "act_mage_black_aoe", "act_mage_fireball", "act_meteor", "act_punched_arrow", "act_rabbit_cleave", "act_rabbit_super_hit", "act_ratman_lord_attack", "act_ratman_lord_frostbolt", "act_ratman_lord_teleport", "act_sag_explosive_arrow", "act_sag_magic_arrow", "act_sag_one_shot", "act_shaman_aoe_heal", "act_shaman_dispell", "act_shaman_monstrous", "act_skeleton_lord_berserk", "act_skeleton_lord_cleave", "act_skeleton_lord_march", "act_skeleton_lord_ring_hit", "act_skeleton_lord_sound_blast", "act_slow_dot", "act_spirit_aoe_heal", "act_summon_bats", "act_summon_fire_elem", "act_summon_old_imp", "act_summon_vampire", "act_teleport", "act_turtle_summon", "act_warlock_curse", "act_warrior_shield_bash", "act_warrior_shield_cover", "act_wizard_fireball"]]], "ExpPerTurn": [["amount", "integer", []]], "Flight": [], "FractionProduceResource": [["bonus/resType", "string", ["food", "research", "gold"]], ["bonus/value", "float", []]], "Healability": [["multiplier", "float", []]], "HealingPower": [["multiplier", "float", []]], "Immunity": [["attackType", "string", ["DeathMagic", "RangedAttack", "CloseAttack", "ElementalMagic", "LifeMagic", "SpiritMagic"]]], "ModifyBuildingProductionPercent": [["bonus/resType", "string", ["gold", "food", "mana"]], ["bonus/value", "float", []]], "ModifyCastingTime": [["modifier", "integer", []]], "ModifyCooldowns": [["amount", "integer", []]], "ModifyGold": [["amount", "integer", []]], "ModifyMana": [["amount", "integer", []]], "ModifyMoveCostTileToTile": [["Tile/tileFrom", "string", ["Dense", "Bad", "High", "HighDense"]], ["Tile/tileTo", "string", ["Flat"]]], "ModifyMovePoints": [["value", "float", []]], "ModifyPower": [["multiplier", "float", []]], "NewAttack": [["attackType", "string", ["ElementalMagic", "DeathMagic", "SpiritMagic", "LifeMagic", "CloseAttack", "RangedAttack"]], ["multiplier", "float", []]], "Poison": [["value", "integer", []]], "ProductionLinearBonus": [["Bonus/resType", "string", ["growth", "food"]], ["Bonus/value", "float", []]], "ProductionSpecialistBonus": [["Bonus/specialist", "string", ["", "Scientist"]], ["Bonus/resType", "string", ["food", "mana", "growth"]], ["Bonus/value", "float", []]], "PutDebuff": [["perkName", "string", ["perk_debuff_rat_weakness", "perk_debuff_slow", "perk_roots"]]], "Regeneration": [["value", "integer", []]], "Resistance": [["attackType", "string", ["ElementalMagic", "RangedAttack", "CloseAttack", "DeathMagic", "SpiritMagic", "LifeMagic"]], ["value", "integer", []]], "SelfDestruct": [], "SelfResurrect": [], "SetHatredStatus": [["statusName", "string", ["invisible", "armored", "beast", "donkey", "paladin"]]], "SetUnitStatus": [["statusName", "string", ["paralized", "armored", "truesight", "forester", "invisible", "fear", "finisher", "fleet", "frenzy", "hitAndRun", "beast", "blessed", "cityfighter", "dead", "shielded", "siege", "weakened", "adaptation", "alien", "avatar", "blind", "block_adaptation", "cover", "donkey", "fearless", "highlander", "in_defence", "paladin", "resting", "wet"]]], "SightRange": [["range", "integer", []]], "SpecialImmunity": [["type", "string", ["bad_enchants", "dispel"]]], "StealResources": [["value", "float", []], ["bonus/resType", "string", ["mana", "gold"]], ["bonus/value", "float", []]], "Vampirism": [["value", "float", []]], "Waterwalk": []}, "perk_types": ["Unit", "Artifact", "Fraction", "Town", "Race"]}'''


def base_schema() -> Schema:
    return Schema.from_json(_BASE_SCHEMA_JSON)


def build_schema(items: Iterable[ET.Element]) -> Schema:
    return merge_items(base_schema(), items)


# ---------------------------------------------------------------------------
# Perk <-> <item>
# ---------------------------------------------------------------------------

def _val(el: ET.Element, tag: str, default: str = "") -> str:
    c = el.find(tag)
    return default if c is None or c.get("value") is None else c.get("value")


def _leaf(tag: str, typ: str, value: str) -> ET.Element:
    e = ET.Element(tag)
    e.set("type", typ)
    e.set("value", value)
    return e


@dataclass
class Perk:
    name: str = ""
    perk_type: str = "Unit"
    mana_upkeep: int = 0
    is_good: bool = True
    is_enchant: bool = False
    is_change_move_type: bool = False
    dlc_id: Optional[str] = None           # None = campi dlcId/dlcIdIdx assenti
    dlc_idx: int = 0
    conditions: List[ET.Element] = field(default_factory=list)
    effects: List[ET.Element] = field(default_factory=list)
    terminators: Optional[ET.Element] = None   # None = nessun blocco <Terminators>

    @classmethod
    def from_element(cls, it: ET.Element) -> "Perk":
        extra = [c.tag for c in it if c.tag not in KNOWN_ITEM_TAGS]
        if extra:
            raise PerkError(f"Il perk ha campi non gestiti dal form: {', '.join(extra)}")
        try:
            mana = int(_val(it, "manaUpkeep", "0"))
            idx = int(_val(it, "dlcIdIdx", "0"))
        except ValueError as exc:
            raise PerkError(f"Valore numerico non valido: {exc}") from exc
        conds = it.find("Conditions")
        effs = it.find("Effects")
        term = it.find("Terminators")
        return cls(
            name=_val(it, "name"), perk_type=_val(it, "perkType"), mana_upkeep=mana,
            is_good=_val(it, "isGood", "0") == "1", is_enchant=_val(it, "isEnchant", "0") == "1",
            is_change_move_type=_val(it, "isChangeMoveType", "0") == "1",
            dlc_id=_val(it, "dlcId") if it.find("dlcId") is not None else None, dlc_idx=idx,
            conditions=[copy.deepcopy(c) for c in (conds if conds is not None else [])],
            effects=[copy.deepcopy(e) for e in (effs if effs is not None else [])],
            terminators=copy.deepcopy(term) if term is not None else None,
        )

    def validate(self) -> None:
        if not NAME_RE.match(self.name or ""):
            raise PerkError("Il nome può contenere solo lettere, cifre e '_' (e non può essere vuoto).")
        if not self.perk_type.strip():
            raise PerkError("Indica il tipo di perk (perkType).")
        if self.mana_upkeep < 0:
            raise PerkError("manaUpkeep non può essere negativo.")
        if not self.conditions:
            raise PerkError("Serve almeno una condizione (tutti i perk del gioco ne hanno una).")

    def to_element(self) -> ET.Element:
        self.validate()
        it = ET.Element("item")
        it.append(_leaf("name", "string", self.name))
        it.append(_leaf("perkType", "string", self.perk_type))
        it.append(_leaf("manaUpkeep", "integer", str(int(self.mana_upkeep))))
        it.append(_leaf("isGood", "bool", "1" if self.is_good else "0"))
        it.append(_leaf("isEnchant", "bool", "1" if self.is_enchant else "0"))
        it.append(_leaf("isChangeMoveType", "bool", "1" if self.is_change_move_type else "0"))
        if self.dlc_id is not None:
            it.append(_leaf("dlcId", "string", self.dlc_id))
            it.append(_leaf("dlcIdIdx", "integer", str(int(self.dlc_idx))))
        conds = ET.SubElement(it, "Conditions")
        for c in self.conditions:
            conds.append(copy.deepcopy(c))
        effs = ET.SubElement(it, "Effects")
        for e in self.effects:
            effs.append(copy.deepcopy(e))
        if self.terminators is not None:
            it.append(copy.deepcopy(self.terminators))
        indent_item(it, 2)
        return it


def client_condition(client: str) -> ET.Element:
    c = ET.Element("ClientConditionData")
    c.append(_leaf("client", "string", client))
    return c


def condition_client(cond: ET.Element) -> Optional[str]:
    if cond.tag == "ClientConditionData" and cond.find("client") is not None:
        return cond.find("client").get("value")
    return None


# --- Terminators -----------------------------------------------------------

@dataclass
class TerminatorsData:
    present: bool = True
    dispellable: bool = False
    timer_turns: Optional[int] = None      # None = niente StrategicTimer
    timer_first: bool = False              # nel file originale StrategicTimer precede Dispellable
    other: List[ET.Element] = field(default_factory=list)   # figli sconosciuti, conservati


def terminators_data(term: Optional[ET.Element]) -> TerminatorsData:
    if term is None:
        return TerminatorsData(present=False)
    td = TerminatorsData(present=True)
    for ch in term:
        if ch.tag == "Dispellable":
            td.dispellable = True
        elif ch.tag == "StrategicTimer" and ch.find("turns") is not None:
            try:
                td.timer_turns = int(ch.find("turns").get("value"))
                td.timer_first = not td.dispellable
            except (TypeError, ValueError):
                td.other.append(copy.deepcopy(ch))
        else:
            td.other.append(copy.deepcopy(ch))
    return td


def terminators_element(td: TerminatorsData) -> Optional[ET.Element]:
    if not td.present:
        return None
    t = ET.Element("Terminators")

    def add_dispellable() -> None:
        if td.dispellable:
            ET.SubElement(t, "Dispellable")

    def add_timer() -> None:
        if td.timer_turns is not None:
            st = ET.SubElement(t, "StrategicTimer")
            st.append(_leaf("turns", "integer", str(int(td.timer_turns))))

    if td.timer_first:
        add_timer(); add_dispellable()
    else:
        add_dispellable(); add_timer()
    for o in td.other:
        t.append(copy.deepcopy(o))
    return t


# --- Effetti ---------------------------------------------------------------

def effect_values(schema: Schema, el: ET.Element) -> Optional[Dict[str, str]]:
    """Valori dei campi di un effetto, o None se la sua forma non rientra nello schema."""
    spec = schema.effects.get(el.tag)
    if spec is None or _is_value_leaf(el):
        return None
    known = {f.path for f in spec.fields}
    out: Dict[str, str] = {}
    for path, leaf in _leaf_paths(el):
        if path not in known or not _is_value_leaf(leaf) or leaf.get("type") != next(
                f.type for f in spec.fields if f.path == path):
            return None
        out[path] = leaf.get("value")
    # i container vuoti (es. <Tile/> senza figli) non rientrano nello schema
    for node in el.iter():
        if node is not el and len(node) == 0 and not _is_value_leaf(node):
            return None
    return out


def normalize_value(typ: str, text: str) -> str:
    t = text.strip()
    if typ == "integer":
        try:
            return str(int(t))
        except ValueError as exc:
            raise PerkError(f"'{text}' non è un numero intero.") from exc
    if typ == "float":
        try:
            f = float(t.replace(",", "."))
        except ValueError as exc:
            raise PerkError(f"'{text}' non è un numero.") from exc
        s = repr(f)
        return s[:-2] + ".0" if s.endswith("e") else s
    if typ == "bool":
        if t not in ("0", "1"):
            raise PerkError("I valori booleani sono 0 o 1.")
        return t
    return text


def effect_element(schema: Schema, tag: str, values: Dict[str, str]) -> ET.Element:
    spec = schema.effects.get(tag)
    if spec is None:
        raise PerkError(f"Tipo di effetto sconosciuto: {tag}")
    root = ET.Element(tag)
    containers: Dict[str, ET.Element] = {}
    for f in spec.fields:
        parts = f.path.split("/")
        parent = root
        for i, p in enumerate(parts[:-1]):
            key = "/".join(parts[: i + 1])
            if key not in containers:
                containers[key] = ET.SubElement(parent, p)
            parent = containers[key]
        raw = values.get(f.path, "")
        if f.type != "string" and raw.strip() == "":
            raise PerkError(f"{tag}: il campo '{f.path}' è obbligatorio.")
        parent.append(_leaf(parts[-1], f.type, normalize_value(f.type, raw)))
    return root


def effect_summary(el: ET.Element) -> str:
    leaves = [(p, l.get("value")) for p, l in _leaf_paths(el) if _is_value_leaf(l)]
    if not leaves and _is_value_leaf(el):
        return f"value={el.get('value')}"
    return ", ".join(f"{p.split('/')[-1]}={v}" for p, v in leaves)


# ---------------------------------------------------------------------------
# Formattazione e lista ordinata
# ---------------------------------------------------------------------------

def indent_item(el: ET.Element, level: int, space: str = "  ") -> None:
    """Indenta come il file: 2 spazi per livello; gli elementi vuoti restano <X>\\n</X>."""
    pad = "\n" + space * level
    child_pad = "\n" + space * (level + 1)
    if len(el):
        el.text = child_pad
        for ch in el:
            indent_item(ch, level + 1, space)
            ch.tail = child_pad
        el[-1].tail = pad
    elif el.get("type") is None and el.get("value") is None:
        el.text = pad


def perk_data_of(root: ET.Element) -> ET.Element:
    pd = root if root.tag == "PerkData" else root.find("PerkData")
    if pd is None:
        raise PerkError("Elemento <PerkData> non trovato in perks.binary.xml.")
    return pd


def item_name(it: ET.Element) -> str:
    return _val(it, "name")


def find_item(pd: ET.Element, name: str) -> Optional[Tuple[int, ET.Element]]:
    for i, it in enumerate(list(pd)):
        if item_name(it) == name:
            return i, it
    return None


def list_names(pd: ET.Element) -> List[str]:
    return [item_name(it) for it in pd]


def inversions(names: List[str]) -> int:
    n = 0
    for key in (lambda s: s, str.lower):
        n += sum(1 for i in range(1, len(names)) if key(names[i - 1]) > key(names[i]))
    return n


def sorted_position(names: List[str], name: str) -> int:
    pos = next((i for i, n in enumerate(names) if n.lower() > name.lower()), len(names))
    for key in (lambda s: s, str.lower):
        if (pos and key(names[pos - 1]) > key(name)) or (pos < len(names) and key(names[pos]) < key(name)):
            raise PerkError(
                f"Il nome '{name}' finisce in un punto diverso della lista a seconda che il confronto "
                "distingua maiuscole e minuscole, e non so quale usi il gioco. Cambia la lettera "
                "iniziale dopo il prefisso (maiuscola o minuscola come i perk vicini) per evitare l'ambiguità."
            )
    return pos


def _fix_tails(pd: ET.Element) -> None:
    items = list(pd)
    if not items:
        return
    mid = items[0].tail if len(items) > 1 and items[0].tail else "\n    "
    last = "\n  "
    for it in items[:-1]:
        it.tail = mid
    items[-1].tail = last


def insert_sorted(pd: ET.Element, item: ET.Element) -> int:
    """Inserisce <item> al suo posto alfabetico. Ritorna l'indice."""
    names = list_names(pd)
    name = item_name(item)
    if name in names:
        raise PerkError(f"Esiste già un perk chiamato '{name}'.")
    if inversions(names):
        raise PerkError(
            f"perks.binary non è in ordine alfabetico ({inversions(names)} inversioni): "
            "usa prima 'Ordina lista'."
        )
    pos = sorted_position(names, name)
    pd.insert(pos, item)
    _fix_tails(pd)
    return pos


def replace_item(pd: ET.Element, name: str, item: ET.Element) -> int:
    found = find_item(pd, name)
    if found is None:
        raise PerkError(f"Perk '{name}' non trovato.")
    idx, _old = found
    if item_name(item) != name:
        raise PerkError("Il nome non si può cambiare in modifica: usa 'Duplica perk'.")
    pd.remove(_old)
    pd.insert(idx, item)
    _fix_tails(pd)
    return idx


def sort_items(pd: ET.Element) -> int:
    """Ordina tutti i perk per nome (stabile). Ritorna quanti elementi sono cambiati di posto."""
    items = list(pd)
    ordered = sorted(items, key=lambda it: (item_name(it).lower(), item_name(it)))
    moved = sum(1 for a, b in zip(items, ordered) if a is not b)
    for it in items:
        pd.remove(it)
    for it in ordered:
        pd.append(it)
    _fix_tails(pd)
    return moved