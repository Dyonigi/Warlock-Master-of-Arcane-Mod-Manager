import struct, sys, zlib
from collections import Counter
T = int(sys.argv[1])
d = open(r'work\unpacked_pack\c_icons.gfx', 'rb').read()
if d[:3] == b'CFX': d = d[:8] + zlib.decompress(d[8:])
pos = 8 + (5 + 4*(d[8] >> 3) + 7)//8 + 4

def tags(b, p=0):
    while p + 2 <= len(b):
        h = struct.unpack_from('<H', b, p)[0]; p += 2
        c, l = h >> 6, h & 63
        if l == 63: l = struct.unpack_from('<I', b, p)[0]; p += 4
        yield c, b[p:p+l]; p += l

def cstr(b, p): return b[p:b.index(b'\0', p)].decode('latin1')
top = list(tags(d, pos))
print("tag top-level:", dict(Counter(c for c, _ in top)))
pat = [bytes([t]) + struct.pack('<H', T) for t in (0x40, 0x41, 0x42, 0x43)]
shapes = {struct.unpack_from('<H', b, 0)[0] for c, b in top if c in (2, 22, 32, 83) and any(p in b for p in pat)}
print("shape che usano il bitmap", T, ":", shapes)
for c, b in top:
    if c == 39:
        sid, nf = struct.unpack_from('<HH', b, 0); fr = 1; lab = {}; plc = []
        for c2, b2 in tags(b, 4):
            if c2 == 1: fr += 1
            elif c2 == 43: lab[fr] = cstr(b2, 0)
            elif c2 == 4: plc.append((fr, struct.unpack_from('<H', b2, 0)[0]))
            elif c2 == 26 and b2[0] & 2: plc.append((fr, struct.unpack_from('<H', b2, 3)[0]))
            elif c2 == 70:
                p = 4
                if b2[1] & 8 or (b2[1] & 16 and b2[0] & 2): p = 4 + len(cstr(b2, 4)) + 1
                if b2[0] & 2: plc.append((fr, struct.unpack_from('<H', b2, p)[0]))
        for f, ch in plc:
            if ch in shapes: print("sprite", sid, "(frame totali", nf, ") frame", f, "label", lab.get(f))
for c, b in top:
    if c in (56, 76):
        n = struct.unpack_from('<H', b, 0)[0]; p = 2; out = []
        for _ in range(n):
            out.append((struct.unpack_from('<H', b, p)[0], cstr(b, p+2))); p += 3 + len(out[-1][1])
        print("tag", c, ":", n, "voci, ultime:", out[-8:], "| con T:", [x for x in out if x[0] in shapes or x[0] == T])