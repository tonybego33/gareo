import sys, math
sys.path.insert(0, '/home/claude/tools')
from dwg import *
from PIL import Image, ImageDraw, ImageFont

def bbox(prims, pct=0.0):
    xs = sorted(p[0] for o in prims if o[0]=='L' for p in o[2]); ys = sorted(p[1] for o in prims if o[0]=='L' for p in o[2])
    k = int(len(xs)*pct)
    return xs[k], ys[k], xs[-1-k], ys[-1-k]

def render(prims, out, W=2400, bb=None, color=lambda o: (0,0,0), text=True, pad=20, lw=1, fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
    x0, y0, x1, y1 = bb or bbox(prims)
    s = (W-2*pad)/max(x1-x0, 1e-9); H = int((y1-y0)*s)+2*pad
    im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im)
    T = lambda p: (pad+(p[0]-x0)*s, H-pad-(p[1]-y0)*s)
    for o in prims:
        if o[0]=='L': dr.line([T(p) for p in o[2]], fill=color(o), width=lw)
    if text:
        for o in prims:
            if o[0]=='T':
                hpx = o[4]*s
                if hpx < 5: continue
                try: f = ImageFont.truetype(fontpath, max(6, int(hpx*1.25)))
                except Exception: f = ImageFont.load_default()
                txt = o[3].replace('\\P',' ')
                import re; txt = re.sub(r'\\[A-Za-z][^;]*;|[{}]', '', txt)
                x, y = T(o[2])
                if abs(o[5]) < 0.05: dr.text((x, y-hpx*1.2), txt, fill=color(o), font=f)
                else:
                    tw = int(dr.textlength(txt, font=f))+4; th = int(hpx*1.6)+4
                    ti = Image.new('RGBA', (tw, th), (255,255,255,0)); ImageDraw.Draw(ti).text((2, 0), txt, fill=color(o)+(255,), font=f)
                    ti = ti.rotate(math.degrees(o[5]), expand=True)
                    im.paste(ti, (int(x), int(y-ti.size[1])), ti)
    im.save(out); return s, (x0, y0, x1, y1), H

def main_bbox(prims, cell=2.0, gap=3, minpts=3):
    from collections import defaultdict
    g = defaultdict(int)
    for o in prims:
        pts = o[2] if o[0] == 'L' else [o[2]]
        for p in pts: g[(int(p[0]//cell), int(p[1]//cell))] += 1
    cells = {k for k, v in g.items() if v >= minpts}
    seen = set(); best = []
    for c in cells:
        if c in seen: continue
        comp = []; st = [c]; seen.add(c)
        while st:
            x, y = st.pop(); comp.append((x, y))
            for dx in range(-gap, gap+1):
                for dy in range(-gap, gap+1):
                    n = (x+dx, y+dy)
                    if n in cells and n not in seen: seen.add(n); st.append(n)
        if sum(g[k] for k in comp) > sum(g[k] for k in best): best = comp
    xs = [k[0] for k in best]; ys = [k[1] for k in best]
    return min(xs)*cell, min(ys)*cell, (max(xs)+1)*cell, (max(ys)+1)*cell
