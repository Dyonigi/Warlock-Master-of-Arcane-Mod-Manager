import struct, zlib
d = open(r'work\unpacked_pack\c_icons.gfx', 'rb').read()
if d[:3] == b'CFX': d = d[:8] + zlib.decompress(d[8:])
pos = 8 + (5 + 4*(d[8] >> 3) + 7)//8 + 4
def tags(b, p=0):
    while p + 2 <= len(b):
        h = struct.unpack_from('<H', b, p)[0]; p += 2
        c, l = h >> 6, h & 63
        if l == 63: l = struct.unpack_from('<I', b, p)[0]; p += 4
        yield c, b[p:p+l]; p += l
top = list(tags(d, pos))
subs = {}
for c, b in top:
    if c == 1008:
        s = struct.unpack_from('<6H', b, 0); subs[s[0]] = s
shape_bmp = {}
for c, b in top:
    if c in (2, 22, 32, 83):
        sid = struct.unpack_from('<H', b, 0)[0]
        for i in range(len(b) - 2):
            if b[i] in (0x40, 0x41, 0x42, 0x43):
                bid = struct.unpack_from('<H', b, i + 1)[0]
                if bid in subs: shape_bmp[sid] = bid; break
def cstr(b, p): return b[p:b.index(b'\0', p)]
for c, b in top:
    if c == 39 and struct.unpack_from('<H', b, 0)[0] == 841:
        fr, cur, lab = 1, [], None
        for c2, b2 in tags(b, 4):
            try:
                if c2 == 43: lab = b2.split(b'\0')[0].decode('latin1')
                elif c2 == 4: cur.append(struct.unpack_from('<H', b2, 0)[0])
                elif c2 == 26 and b2[0] & 2: cur.append(struct.unpack_from('<H', b2, 3)[0])
                elif c2 == 70:
                    p = 4
                    if b2[1] & 8 or (b2[1] & 16 and b2[0] & 2): p += len(cstr(b2, 4)) + 1
                    if b2[0] & 2: cur.append(struct.unpack_from('<H', b2, p)[0])
            except Exception: pass
            if c2 == 1:
                print("frame", fr, "label", lab, [(ch, shape_bmp.get(ch), subs.get(shape_bmp.get(ch), (0,)*6)[2:]) for ch in cur])
                fr += 1; cur, lab = [], None