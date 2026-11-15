"""Elenca in quali pack del gioco compaiono i file dei perk (ordine di caricamento).
Autonomo: si può lanciare da qualsiasi cartella.
Uso:  python where.py "C:\\...\\Warlock - Master of the Arcane" ["*wizard*" "*mage*" ...]
Senza altri argomenti cerca perks*, fractions*, c_icons.gfx, locdata.md.
"""
import fnmatch
import os
import struct
import sys

PREFIX_ORDER = ("s", "l", "m", "d")


def sort_key(name):
    stem, _, ext = name.lower().partition(".")
    if ext != "pack" or len(stem) < 2:
        return (99, 0, name)
    try:
        num = int(stem[1:])
    except ValueError:
        num = 0
    grp = PREFIX_ORDER.index(stem[0]) if stem[0] in PREFIX_ORDER else 50
    return (grp, num, name)


def list_pack(path):
    out = []
    with open(path, "rb") as f:
        n, _ = struct.unpack("<II", f.read(8))
        for _ in range(n):
            buf = f.read(0x80)
            if len(buf) < 0x80:
                break
            name = buf.split(b"\0", 1)[0].decode("latin-1")
            size = struct.unpack("<IIIIIII", f.read(28))[0]
            out.append((name, size))
    return out


game = sys.argv[1] if len(sys.argv) > 1 else "."
pats = [a.lower() for a in sys.argv[2:]] or ["perks*", "fractions*", "c_icons.gfx", "locdata.md"]
packs = sorted((f for f in os.listdir(game) if f.lower().endswith(".pack")), key=sort_key)
for pk in packs:
    try:
        hits = [f"{n} ({s} B)" for n, s in list_pack(os.path.join(game, pk))
                if any(fnmatch.fnmatch(n.lower(), p) for p in pats)]
    except Exception as exc:
        print(f"{pk:12s} illeggibile: {exc}")
        continue
    if hits:
        print(f"{pk:12s}", "; ".join(hits))