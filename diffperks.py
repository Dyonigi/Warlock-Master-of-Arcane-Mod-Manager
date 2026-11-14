"""Diagnostica perk (v2): mostra lo stato EFFETTIVO nel gioco di Trader/Magnate/Butcher.

Da lanciare dalla cartella del progetto (dove c'è txml.py):
    python diffperks.py "C:\\...\\Warlock - Master of the Arcane"

Mostra, per i file effettivi (ultimo pack che li contiene):
  1. fractions.binary: i blocchi Improvement dei perk di fazione (nome, perk, costo) e
     quante volte ciascuno è referenziato nelle liste;
  2. perks.binary: effetti di Looter (Trader), Magnate, Butcher;
  3. perksviewdatalist.binary: struttura e righe che nominano questi perk/effetti;
  4. testi (locdata) delle chiavi FRACTIONPERK_* in l100.pack e in l100.pack.bak.
"""
import difflib
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from packio import list_pack, read_entry          # noqa: E402
from catalog import pack_sort_key                  # noqa: E402
from txml import is_txml, txml_to_xml_string       # noqa: E402

PERKS = ("fractionPerk_Looter", "fractionPerk_Magnate", "fractionPerk_Butcher")
KEYS = ("LOOTER", "MAGNATE", "BUTCHER")


def effective(game, name):
    """(nome pack, byte) del file nell'ultimo pack che lo contiene."""
    found = None
    packs = sorted((f for f in os.listdir(game) if f.lower().endswith(".pack")), key=pack_sort_key)
    for pk in packs:
        try:
            for e in list_pack(os.path.join(game, pk)):
                if e.name.lower() == name:
                    found = (pk, read_entry(os.path.join(game, pk), e))
        except Exception:
            pass
    if found is None:
        raise SystemExit(f"{name} non trovato in nessun pack")
    return found


def xml_of(game, name):
    pk, data = effective(game, name)
    return pk, (txml_to_xml_string(data) if is_txml(data) else data.decode("utf-8", "replace"))


def pretty(el):
    el = ET.fromstring(ET.tostring(el))
    ET.indent(el, space="  ")
    return ET.tostring(el, encoding="unicode").splitlines()


def val(el, tag):
    c = el.find(tag)
    return None if c is None else c.get("value")


def section_fractions(game):
    pk, text = xml_of(game, "fractions.binary")
    print(f"== 1. fractions.binary effettivo: {pk}")
    root = ET.fromstring(text)
    refs = {}
    for it in root.iter("Item"):
        v = it.get("value")
        if v and v.startswith("adv_"):
            refs[v] = refs.get(v, 0) + 1
    rows = []
    for imp in root.iter("Improvement"):
        n = val(imp, "name")
        if n and n.startswith("adv_fractionPerk"):
            rows.append((n, val(imp, "perk"), val(imp, "cost"), refs.get(n, 0)))
    print(f"{'improvement':36s} {'perk':26s} costo  riferimenti")
    for n, perk, cost, r in rows:
        flag = "" if perk and n == "adv_" + perk else "   <-- nome e perk non coincidono"
        print(f"{n:36s} {str(perk):26s} {str(cost):5s}  {r}{flag}")
    orphan = [n for n in refs if n.startswith("adv_fractionPerk") and n not in {r[0] for r in rows}]
    print("referenziati ma senza blocco Improvement:", orphan)


def section_perks(game):
    pk, text = xml_of(game, "perks.binary")
    print(f"\n== 2. perks.binary effettivo: {pk}")
    root = ET.fromstring(text)
    names = {}
    for it in root.iter("item"):
        n = val(it, "name")
        if n:
            names.setdefault(n, []).append(it)
    for p in PERKS:
        if p not in names:
            print(f"{p}: ASSENTE")
            continue
        eff = names[p][0].find("Effects")
        desc = []
        for e in eff:
            b = e.find("bonus")
            desc.append(e.tag + (" " + str([(c.tag, c.get("value")) for c in b]) if b is not None else ""))
        print(f"{p}: {len(names[p])} voce/i | effetti: {desc}")


def section_view(game):
    pk, text = xml_of(game, "perksviewdatalist.binary")
    lines = text.splitlines()
    print(f"\n== 3. perksviewdatalist.binary effettivo: {pk} ({len(lines)} righe)")
    root = ET.fromstring(text)
    print("radice:", root.tag, "| figli:", sorted({c.tag for c in root}))
    first = next(iter(root.iter("item")), None)
    if first is not None:
        print("primo item:")
        for ln in pretty(first)[:25]:
            print("   ", ln)
    keys = PERKS + ("FractionProduceResource", "ModifyBuildingProductionPercent", "Looter", "Magnate", "Butcher")
    shown = 0
    for i, ln in enumerate(lines, 1):
        if any(k.lower() in ln.lower() for k in keys) and shown < 25:
            print(f"  riga {i}: {ln.strip()}")
            shown += 1
    if shown == 0:
        print("nessuna riga nomina questi perk/effetti")


def section_loc(game):
    print("\n== 4. testi locdata delle chiavi FRACTIONPERK_*")
    try:
        from panels.locdata_keys import all_pairs
    except ImportError:
        from locdata_keys import all_pairs
    for label, fname in (("l100.pack", "l100.pack"), ("l100.pack.bak", "l100.pack.bak")):
        path = os.path.join(game, fname)
        if not os.path.isfile(path):
            print(f"{label}: non presente")
            continue
        try:
            data = next(read_entry(path, e) for e in list_pack(path) if e.name.lower() == "locdata.md")
            pairs = dict(all_pairs(data))
        except Exception as exc:
            print(f"{label}: non letto ({exc})")
            continue
        print(f"{label}: {len(pairs)} chiavi")
        for k in KEYS:
            for suffix in ("", "_DESC"):
                key = f"FRACTIONPERK_{k}{suffix}"
                t = pairs.get(key)
                print(f"   {key:30s} {('(assente)' if t is None else repr(t[:70]))}")


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "."
    for fn in (section_fractions, section_perks, section_view, section_loc):
        try:
            fn(game)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[{fn.__name__}] errore: {type(exc).__name__}: {exc}")
