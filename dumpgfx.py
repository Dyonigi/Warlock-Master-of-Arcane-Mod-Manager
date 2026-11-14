import struct, sys, zlib, re
d = open(sys.argv[1], 'rb').read()
if d[:3] == b'CFX':
    d = d[:8] + zlib.decompress(d[8:])
pos = 8
nb = d[pos] >> 3
pos += (5 + 4*nb + 7)//8 + 4
ext, subs, names, labels = {}, [], [], []
while pos + 2 <= len(d):
    h = struct.unpack_from('<H', d, pos)[0]; pos += 2
    code, ln = h >> 6, h & 0x3f
    if ln == 0x3f:
        ln = struct.unpack_from('<I', d, pos)[0]; pos += 4
    b = d[pos:pos+ln]; pos += ln
    if code in (1001, 1009):
        m = re.findall(rb'[\w\-\. ]{3,}', b[8:])
        ext[struct.unpack_from('<H', b, 0)[0]] = (code, [x.decode('latin1') for x in m], b[:12].hex())
    elif code == 1008:
        subs.append(struct.unpack_from('<6H', b, 0))
    elif code == 56:
        n = struct.unpack_from('<H', b, 0)[0]; p = 2
        for _ in range(n):
            i = struct.unpack_from('<H', b, p)[0]; p += 2
            e = b.index(b'\0', p); names.append((i, b[p:e].decode('latin1'))); p = e + 1
    elif code == 43:
        labels.append(b.rstrip(b'\0').decode('latin1'))
print("IMMAGINI ESTERNE (id: tag, stringhe, primi byte)")
for k, v in ext.items():
    if any('icons_i7' in s for s in v[1]): print("  >>", k, v)
print("n. immagini esterne:", len(ext), "| sub-immagini:", len(subs), "| export:", len(names), "| label:", len(labels))
open('gfx_dump.txt', 'w').write(
    "EXT\n" + "\n".join(f"{k} {v}" for k, v in ext.items()) +
    "\nSUB (6 uint16)\n" + "\n".join(map(str, subs)) +
    "\nEXPORT\n" + "\n".join(f"{i} {n}" for i, n in names) +
    "\nLABELS\n" + "\n".join(labels))