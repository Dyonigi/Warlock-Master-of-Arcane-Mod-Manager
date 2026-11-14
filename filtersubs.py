import re
t = open('gfx_dump.txt').read()
subs = [tuple(map(int, m)) for m in re.findall(r'^\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+)\)', t, re.M)]
print("primi 8:", subs[:8])
for pos in (0, 1):
    s = [x for x in subs if x[pos] == 1]
    print("campo", pos, "== 1:", len(s))
    print(s[:12])