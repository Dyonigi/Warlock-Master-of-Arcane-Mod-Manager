import os
from packio import list_pack, read_entry
game = r"C:\Applicazioni\Giochi\Steam\Steam\steamapps\common\Warlock - Master of the Arcane"
for n in sorted(os.listdir(game)):
    if not n.lower().endswith(".pack"):
        continue
    p = os.path.join(game, n)
    for e in list_pack(p):
        name = e.name.lower()
        if ("loc" in name or name.endswith(".md")) and not name.endswith(".fsb"):
            print(n, e.name, e.size, read_entry(p, e)[:16])