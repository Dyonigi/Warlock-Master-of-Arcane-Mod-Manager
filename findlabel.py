"""Cerca nei file .gfx dei pack del gioco le stringhe (label/nomi esportati) che contengono
certe parole. Autonomo: si può lanciare da qualsiasi cartella.
Uso:  python findlabel.py "C:\\...\\Warlock - Master of the Arcane" wizard dark_elf lich
"""
import os
import re
import struct
import sys
import zlib

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


def entries(path):
    out = []
    with open(path, "rb") as f:
        n, _ = struct.unpack("<II", f.read(8))
        for _ in range(n):
            buf = f.read(0x80)
            if len(buf) < 0x80:
                break
            name = buf.split(b"\0", 1)[0].decode("latin-1")
            size, zsize, offset, _x, _y, _z, zipped = struct.unpack("<IIIIIII", f.read(28))
            out.append((name, size, zsize, offset, zipped))
    return out


def read(path, e):
    _name, size, zsize, offset, zipped = e
    with open(path, "rb") as f:
        f.seek(offset)
        return zlib.decompress(f.read(zsize)) if zipped else f.read(size)


def main():
    game = sys.argv[1]
    words = [w.lower() for w in sys.argv[2:]]
    if not words:
        raise SystemExit("Indica almeno una parola da cercare.")
    packs = sorted((f for f in os.listdir(game) if f.lower().endswith(".pack")), key=sort_key)
    total = 0
    for pk in packs:
        path = os.path.join(game, pk)
        for e in entries(path):
            if not e[0].lower().endswith(".gfx"):
                continue
            data = read(path, e)
            if data[:3] == b"CFX":
                try:
                    data = data[:8] + zlib.decompress(data[8:])
                except zlib.error:
                    continue
            found = set()
            for w in words:
                for m in re.finditer(rb"[A-Za-z0-9_.\-]*" + re.escape(w.encode()) + rb"[A-Za-z0-9_.\-]*", data, re.I):
                    found.add(m.group(0).decode("latin-1"))
            if found:
                total += 1
                print(f"{pk:10s} {e[0]} ({e[1]} B): {sorted(found)[:25]}")
    if not total:
        print("Nessuna corrispondenza nei file .gfx.")


if __name__ == "__main__":
    main()