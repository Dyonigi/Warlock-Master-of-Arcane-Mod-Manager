#!/usr/bin/env python3
"""Sostituisce UN file dentro un .pack lasciando tutte le altre entry identiche.

Uso:
    python patch_pack.py <pack> <nome_nel_pack> <file_nuovo>
Esempio:
    python patch_pack.py "C:\\...\\Warlock - Master of the Arcane\\l100.pack" locdata.md locdata.md

Prima di scrivere crea <pack>.bak (solo se non esiste già): non sovrascrive mai
il backup, quindi si può rilanciare più volte partendo sempre dall'originale.
Le altre entry vengono copiate byte per byte (stessi byte compressi, stessi
campi x/y/z e flag di compressione); dell'entry sostituita si mantengono
x/y/z e il flag di compressione originali.
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
import zlib
from typing import List

from packio import (
    FILE_NAME_BUFFER_SIZE,
    FILE_RECORD_INFO_FMT,
    FILE_RECORD_SIZE,
    PACK_FILE_HEADER_FMT,
    list_pack,
)


def replace_in_pack(src_pack: str, name: str, new_data: bytes, out_pack: str) -> None:
    entries = list_pack(src_pack)
    if not any(e.name == name for e in entries):
        raise SystemExit(f"'{name}' non trovato in {src_pack}")

    with open(src_pack, "rb") as f:
        nr_files, unknown = struct.unpack("<" + PACK_FILE_HEADER_FMT, f.read(8))

    with open(src_pack, "rb") as src, open(out_pack, "wb") as out:
        out.write(struct.pack("<" + PACK_FILE_HEADER_FMT, nr_files, unknown))
        records_start = out.tell()
        out.write(b"\0" * (len(entries) * FILE_RECORD_SIZE))
        blob_offset = out.tell()

        records: List[bytes] = []
        for e in entries:
            if e.name == name:
                size = len(new_data)
                stored = zlib.compress(new_data) if e.is_zipped else new_data
            else:
                src.seek(e.offset)
                stored = src.read(e.zsize if e.is_zipped else e.size)
                size = e.size
            out.seek(blob_offset)
            out.write(stored)

            name_buf = e.name.encode("latin-1")
            name_buf += b"\0" * (FILE_NAME_BUFFER_SIZE - len(name_buf))
            records.append(
                name_buf
                + struct.pack(
                    "<" + FILE_RECORD_INFO_FMT,
                    size,
                    len(stored),
                    blob_offset,
                    e.x,
                    e.y,
                    e.z,
                    1 if e.is_zipped else 0,
                )
            )
            blob_offset += len(stored)

        out.seek(records_start)
        out.write(b"".join(records))


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    pack, name, new_file = sys.argv[1:4]
    with open(new_file, "rb") as f:
        new_data = f.read()

    bak = pack + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(pack, bak)
        print(f"Backup creato: {bak}")
    tmp = pack + ".tmp"
    # parte SEMPRE dal backup (originale), così le modifiche non si accumulano
    replace_in_pack(bak, name, new_data, tmp)
    os.replace(tmp, pack)
    print(f"{name} sostituito in {pack}")


if __name__ == "__main__":
    main()