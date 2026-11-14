import struct, zlib
d = open(r'work\unpacked_pack\c_icons.gfx', 'rb').read()
if d[:3] == b'CFX': d = d[:8] + zlib.decompress(d[8:])
print("firma, versione, lunghezza dichiarata, reale:", d[:3], d[3], struct.unpack_from('<I', d, 4)[0], len(d))
pos = 8 + (5 + 4*(d[8] >> 3) + 7)//8 + 4
def tags(b, p=0):
    while p + 2 <= len(b):
        s = p; h = struct.unpack_from('<H', b, p)[0]; p += 2
        c, l = h >> 6, h & 63; lng = False
        if l == 63: l = struct.unpack_from('<I', b, p)[0]; p += 4; lng = True
        yield c, b[p:p+l], s, lng; p += l
for c, b, s, lng in tags(d, pos):
    if c == 39 and struct.unpack_from('<H', b, 0)[0] == 841:
        print("sprite 841: offset", s, "| lunghezza", len(b), "| header lungo:", lng, "| frame dichiarati:", struct.unpack_from('<H', b, 2)[0])
        fr = 1
        for c2, b2, s2, l2 in tags(b, 4):
            if fr in (6, 7, 8, 21, 22): print("frame", fr, "| tag", c2, "| len", len(b2), "| lungo", l2, "|", b2[:20].hex())
            if c2 == 1: fr += 1