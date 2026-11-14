import re, sys
from PIL import Image, ImageDraw
t = open('gfx_dump.txt').read()
subs = [tuple(map(int, m)) for m in re.findall(r'^\((\d+), (\d+), (\d+), (\d+), (\d+), (\d+)\)', t, re.M)]
subs = [s for s in subs if s[1] == 1]
if len(sys.argv) == 3:                       # python sheet.py X Y -> id del ritaglio che contiene il punto
    x, y = int(sys.argv[1]), int(sys.argv[2])
    print([s for s in subs if s[2] <= x < s[4] and s[3] <= y < s[5]]); sys.exit()
im = Image.open(r'work\unpacked_pack\c_icons_i7.dds').convert('RGBA')
print("dimensioni atlante:", im.size)
cols, T = 12, 96
sheet = Image.new('RGBA', (cols*T, ((len(subs)+cols-1)//cols)*(T+14)), (40, 40, 40, 255))
d = ImageDraw.Draw(sheet)
for i, (sid, _, x1, y1, x2, y2) in enumerate(subs):
    c = im.crop((x1, y1, x2, y2)).resize((T-4, T-4))
    ox, oy = (i % cols)*T, (i//cols)*(T+14)
    sheet.paste(c, (ox+2, oy+14), c)
    d.text((ox+3, oy+1), str(sid), fill=(255, 255, 0, 255))
sheet.save('sheet.png')