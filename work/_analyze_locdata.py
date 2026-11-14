#!/usr/bin/env python3
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
data = open(
    r"C:\Applicazioni\Giochi\Steam\Steam\steamapps\common\Warlock - Master of the Arcane\mods\warlock_mod_manager\work\l100_unpacked\locdata.md",
    "rb",
).read()
NUL = b"\x00"


def parse_records(buf: bytes):
    recs = []
    i = 0
    while True:
        j = buf.find(b"#", i)
        if j < 0:
            break
        if j + 1 >= len(buf) or not (65 <= buf[j + 1] <= 90):
            i = j + 1
            continue
        z = buf.find(NUL, j + 1)
        if z < 0:
            break
        key = buf[j + 1 : z].decode("latin-1")
        if len(key) < 2 or not all(c.isalnum() or c == "_" for c in key):
            i = j + 1
            continue
        p = z + 1
        if p < len(buf) and buf[p : p + 1] == b"#":
            val = ""
            nxt = p
        else:
            z2 = buf.find(NUL, p)
            if z2 < 0:
                val = buf[p:].decode("latin-1")
                nxt = len(buf)
            else:
                val = buf[p:z2].decode("latin-1")
                nxt = z2 + 1
        recs.append((key, val, j, nxt))
        i = nxt
    return recs


recs = parse_records(data)
print("records", len(recs))
print("first", recs[0][:2], "off", recs[0][2])
print("last", recs[-1][:2], "off", recs[-1][2])
print("Q_", sum(1 for r in recs if r[0].startswith("Q_")))
print("span", recs[0][2], recs[-1][3], "len", recs[-1][3] - recs[0][2])

fo = recs[0][2]
# search pointer = base + file_offset for first 3 keys
offs = [recs[i][2] for i in (0, 1, 5)]
print("sample offs", offs)

# Scan all uint32 in the pre-string region; collect those that as (x - fo) are constant across keys
# Instead: for every uint32 in file, compute base = u32 - fo, see if other key offsets exist as base+off
pre = data[:fo]
found_bases = []
for i in range(0, len(pre) - 4, 4):
    v = struct.unpack_from("<I", pre, i)[0]
    base = (v - fo) & 0xFFFFFFFF
    # check second key
    ptr2 = (base + offs[1]) & 0xFFFFFFFF
    packed = struct.pack("<I", ptr2)
    if packed in pre:
        ptr3 = (base + offs[2]) & 0xFFFFFFFF
        if struct.pack("<I", ptr3) in pre:
            found_bases.append((base, i, v))
            if len(found_bases) >= 8:
                break
print("bases", [(hex(b), hex(at), hex(v)) for b, at, v in found_bases[:8]])

# Maybe pointers are 64-bit
found64 = []
for i in range(0, min(len(pre), 200000) - 8, 4):
    v = struct.unpack_from("<Q", pre, i)[0]
    if v > 0xFFFFFFFF:
        continue
    base = (v - fo) & 0xFFFFFFFFFFFFFFFF
    ptr2 = base + offs[1]
    if 0 < ptr2 < 0xFFFFFFFF and struct.pack("<I", ptr2) in pre[i : i + 200]:
        found64.append((i, v, base))
        if len(found64) > 5:
            break
print("maybe64", found64[:5])

# Dump 12-byte stride table immediately before string blob
print("before strings hex")
print(data[fo - 96 : fo].hex())

# Look at 8-byte records ending at fo
print("--- 12-byte window before fo ---")
for recsz in (8, 12, 16):
    # last 6 records
    print("recsz", recsz)
    for n in range(6, 0, -1):
        o = fo - n * recsz
        ints = struct.unpack_from("<" + "I" * (recsz // 4), data, o)
        print(" ", ints)

# Header interpretation: maybe after magic+size, an array of {uint64 count or ptr}
print("header as 8-byte pairs from +8")
for i in range(8, 0x80, 8):
    a, b = struct.unpack_from("<II", data, i)
    print(f"  +{i:02x} {a:8d} {b:8d}  {a:08x} {b:08x}")
