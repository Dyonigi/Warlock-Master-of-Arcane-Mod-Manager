#!/usr/bin/env python3
"""Read and write Warlock .pack archives (binary, zlib-compressed files)."""

from __future__ import annotations

import fnmatch
import os
import struct
import zlib
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


PACK_FILE_HEADER_FMT = "II"
FILE_NAME_BUFFER_SIZE = 0x80
FILE_RECORD_INFO_FMT = "IIIIIII"
FILE_RECORD_SIZE = FILE_NAME_BUFFER_SIZE + struct.calcsize("<" + FILE_RECORD_INFO_FMT)


@dataclass
class PackEntry:
    name: str
    size: int
    zsize: int
    offset: int
    x: int
    y: int
    z: int
    is_zipped: bool


def _read_unpack(fd, fmt: str):
    return struct.unpack("<" + fmt, fd.read(struct.calcsize(fmt)))


def list_pack(pack_path: str) -> List[PackEntry]:
    entries: List[PackEntry] = []
    with open(pack_path, "rb") as fd:
        nr_files, _unknown = _read_unpack(fd, PACK_FILE_HEADER_FMT)
        for _ in range(nr_files):
            name_buf = fd.read(FILE_NAME_BUFFER_SIZE)
            if len(name_buf) < FILE_NAME_BUFFER_SIZE:
                break
            name = name_buf.split(b"\0", 1)[0].decode("latin-1")
            size, zsize, offset, x, y, z, is_zipped = _read_unpack(fd, FILE_RECORD_INFO_FMT)
            entries.append(
                PackEntry(name, size, zsize, offset, x, y, z, bool(is_zipped))
            )
    return entries


def read_entry(pack_path: str, entry: PackEntry) -> bytes:
    with open(pack_path, "rb") as fd:
        fd.seek(entry.offset)
        if entry.is_zipped:
            data = zlib.decompress(fd.read(entry.zsize))
            if len(data) != entry.size:
                raise ValueError(f"Decompressed size mismatch for {entry.name}")
            return data
        return fd.read(entry.size)


def unpack_pack(pack_path: str, dest_dir: str, names: Optional[Iterable[str]] = None) -> List[str]:
    os.makedirs(dest_dir, exist_ok=True)
    wanted = set(names) if names is not None else None
    written: List[str] = []
    for entry in list_pack(pack_path):
        if wanted is not None and entry.name not in wanted:
            continue
        data = read_entry(pack_path, entry)
        out_path = os.path.join(dest_dir, entry.name)
        os.makedirs(os.path.dirname(out_path) or dest_dir, exist_ok=True)
        with open(out_path, "wb") as out:
            out.write(data)
        written.append(out_path)
    return written


def pack_dir(src_dir: str, pack_path: str, no_zip_patterns: Sequence[str] = ()) -> None:
    file_list = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if os.path.isfile(os.path.join(src_dir, f))
    ]
    nr_files = len(file_list)
    with open(pack_path, "wb") as fd:
        fd.write(struct.pack("<" + PACK_FILE_HEADER_FMT, nr_files, 0))
        record_start = fd.tell()
        fd.write(b"\0" * (nr_files * FILE_RECORD_SIZE))
        blob_offset = fd.tell()
        record_offset = record_start
        for fpath in file_list:
            name = os.path.basename(fpath)
            if len(name.encode("latin-1")) > FILE_NAME_BUFFER_SIZE:
                raise ValueError(f"File name too long for pack: {name}")
            use_zip = True
            for p in no_zip_patterns:
                if fnmatch.fnmatch(name, p):
                    use_zip = False
                    break
            with open(fpath, "rb") as src:
                data = src.read()
            size = len(data)
            packed = zlib.compress(data) if use_zip else data
            zsize = len(packed)
            name_buf = name.encode("latin-1")
            name_buf = name_buf + b"\0" * (FILE_NAME_BUFFER_SIZE - len(name_buf))
            fd.seek(record_offset)
            fd.write(name_buf)
            fd.write(
                struct.pack(
                    "<" + FILE_RECORD_INFO_FMT,
                    size,
                    zsize,
                    blob_offset,
                    0,
                    0xFFFFFFFF,
                    0xFFFFFFFF,
                    1 if use_zip else 0,
                )
            )
            record_offset = fd.tell()
            fd.seek(blob_offset)
            fd.write(packed)
            blob_offset = fd.tell()
