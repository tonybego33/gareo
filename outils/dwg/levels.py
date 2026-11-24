"""Plans par niveau de la gare de Toulon à partir des DWG 007291z (lecture directe)."""
import sys, pickle, math, re
sys.path.insert(0, '/home/claude/tools')
from PIL import Image, ImageDraw, ImageFont
from xform import xf_prims

R = pickle.load(open('/home/claude/in/prims.pkl', 'rb'))
G = pickle.load(open('/home/claude/in/reg.pkl', 'rb'))
FOOT = pickle.load(open('/home/claude/in/foot.pkl', 'rb'))
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/in/plans_tln'

X0, Y0, X1, Y1 = -1112.0, 1851.0, -938.0, 1927.0
W = 4400; SS = 2
H = int(round(W * (Y1 - Y0) / (X1 - X0)))
S = W * SS / (X1 - X0)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_fc = {}
def font(px, bold=False):
    k = (int(px), bold)
    if k not in _fc: _fc[k] = ImageFont.truetype(FONTB if bold else FONT, max(6, int(px)))
    return _fc[k]

def T(p): return ((p[0] - X0) * S, (Y1 - p[1]) * S)

def _mid(o):
    if o[0] == 'T': return o[2]
    xs = [p[0] for p in o[2]]; ys = [p[1] for p in o[2]]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
def _in(p, b): return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]
TITLE = re.compile(r'007291Z_|008631g|TOULON GARE|^BATIMENT\s*\d+', re.I)
def _strip_titles(P):
    boxes = []
    for o in P:
        if o[0] == 'T' and TITLE.search(clean(o[3])) and not clean(o[3]).upper().startswith('BATIMENT'):
            h = o[4]; x, y = o[2]; L = len(clean(o[3])) * h * 0.8
            boxes.append((x - 1.5 * h, y - 1.5 * h, x + L + 1.5 * h, y + 2.5 * h))
    out = []
    for o in P:
        if o[0] == 'T' and TITLE.search(clean(o[3])): continue
        if o[0] == 'L' and any(all(_in(p, b) for p in o[2]) for b in boxes): continue
        out.append(o)
    return out
def level(spec):
    """spec : [(clé, emprise ou None)] ; la première clé sert de base hors emprises."""
    regions = [b for _, b in spec if b]
    P = []
    for k, b in spec:
        Q = xf_prims(R[k], *G[k][1]) if k in G else R[k]
        Q = _strip_titles(Q)
        if b: Q = [o for o in Q if _in(_mid(o), b)]
        elif regions: Q = [o for o in Q if not any(_in(_mid(o), rb) for rb in regions)]
        P += Q
    seen = set(); texts = {}; out = []
    for o in P:
        if o[0] == 'L':
            key = tuple((round(x, 2), round(y, 2)) for x, y in o[2])
            if key in seen or key[::-1] in seen: continue
            seen.add(key)
        else:
            t = clean(o[3]); near = texts.setdefault(t, [])
            if any(math.hypot(o[2][0] - q[0], o[2][1] - q[1]) < 1.0 for q in near): continue
            near.append(o[2])
        out.append(o)
    return out

def clean(t):
    t = re.sub(r'\\[Pp]', '\n', t)
    t = re.sub(r'\\[A-Za-z][^;\\{}]*;', '', t)
    t = re.sub(r'\\[A-Za-z]', '', t)
    t = t.replace('{', '').replace('}', '').replace('%%c', 'Ø').replace('%%d', '°')
    return '\n'.join(l.strip() for l in t.split('\n') if l.strip())

NOISE = re.compile(r'^(GA|LE|\d+CM|\d{4,5}|0|999|\d+[A-Z]{2,3}|[A-Z]{1,2}\d{0,2}|\d+ ?m²|\d+(\.\d+)? ?m)$')

def anchor_of(o):
    r = o[-1] if isinstance(o[-1], dict) else {}
    if r.get('name') == 'MTEXT':
        a = (r.get('att') or 1) - 1
        return [0, .5, 1][a % 3], [0, .5, 1][min(2, a // 3)]
    ha = r.get('ha', 0); va = r.get('va', 0)
    hf = {0: 0, 1: .5, 2: 1, 4: .5}.get(ha, 0)
    vf = {0: .85, 1: 1, 2: .5, 3: 0}.get(va, .85)
    if ha == 4: vf = .5
    return hf, vf

def draw_text(im, x, y, txt, px, rot, hf, vf, fill, halo=True, bold=False):
    f = font(px, bold)
    lines = txt.split('\n')
    d0 = ImageDraw.Draw(im)
    tw = int(max(d0.textlength(l, font=f) for l in lines)) + 4
    lh = int(px * 1.18); th = lh * len(lines) + 4
    side = int(math.hypot(tw, th) * 2) + 8
    tile = Image.new('LA', (side, side), (255, 0))
    dt = ImageDraw.Draw(tile)
    ox = side / 2 - hf * tw; oy = side / 2 - vf * th
    for i, l in enumerate(lines):
        if halo:
            dt.text((ox + 2, oy + 2 + i * lh), l, font=f, fill=(255, 255), stroke_width=max(2, int(px / 6)), stroke_fill=(255, 255))
    for i, l in enumerate(lines):
        dt.text((ox + 2, oy + 2 + i * lh), l, font=f, fill=(fill, 255))
    if abs(rot) > 0.01: tile = tile.rotate(math.degrees(rot), resample=Image.BICUBIC, center=(side / 2, side / 2))
    im.paste(tile.convert('L'), (int(x - side / 2), int(y - side / 2)), tile.split()[1])

def render(main, ghost, name, labels=(), minpx=7):
    im = Image.new('L', (W * SS, H * SS), 255); dr = ImageDraw.Draw(im)
    for o in ghost:
        if o[0] == 'L': dr.line([T(p) for p in o[2]], fill=236, width=SS)
    for o in main:
        if o[0] == 'L': dr.line([T(p) for p in o[2]], fill=40, width=SS)
    n = 0
    for o in main:
        if o[0] != 'T': continue
        r = o[-1] if isinstance(o[-1], dict) else {}
        txt = clean(o[3])
        if not txt or NOISE.match(txt): continue
        if r.get('name') == 'ATTRIB' and not re.fullmatch(r'\d{3}', txt): continue
        px = o[4] * S / 0.72
        if px < minpx * SS: continue
        px = min(px, 34 * SS)
        hf, vf = anchor_of(o)
        x, y = T(o[2])
        draw_text(im, x, y, txt, px, o[5], hf, vf, 20); n += 1
    for (txt, wx, wy, px) in labels:
        x, y = T((wx, wy))
        draw_text(im, x, y, txt, px * SS, 0, .5, .5, 0, bold=True)
    im = im.resize((W, H), Image.LANCZOS)
    im.save(f'{OUT}/{name}.jpg', quality=80, optimize=True)
    print(name, W, H, 'textes', n)

if __name__ == '__main__':
    import os; os.makedirs(OUT, exist_ok=True)
    F = FOOT; pad = lambda b, m=0.6: (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    B035 = (-1075.0, 1865.5, -1053.4, 1890.5)
    rdc = level([('020_00', None), ('014_00', pad(F['014_00'])), ('015_00', pad(F['015_00'])), ('035_00', B035), ('037_00', pad(F['037_00']))])
    r1 = level([('015_01', None), ('020_01', pad(F['020_02']))])
    r2 = level([('020_02', None)])
    ss = level([('015_s1', None), ('020_s1', None), ('035_s1', None)])
    ghost_rdc = [o for o in rdc if o[0] == 'L']
    def blabel(k, txt, dy=-2.2):
        b = FOOT[k]; return (txt, (b[0] + b[2]) / 2, b[1] + dy, 30)
    bl = [blabel('014_00', 'B014'), ('B035', -1064.0, 1866.6, 30), blabel('015_00', 'B015 · Bâtiment voyageurs'),
          ('B020', -951.7, 1887.4, 30), ('B037 · véranda', -953.1, 1858.6, 26)]
    quais = [('Quai 3 · voies D-E', -1042.0, 1919.85, 30), ('Quai 2 · voies B-C', -1042.0, 1906.35, 30), ('Quai 1 · voie A', -1031.0, 1890.5, 30)]
    TT = lambda t: (t, -1101.0, 1924.6, 40)
    render(rdc, [], 'RDC', bl + quais + [TT('RDC · quais')])
    render(ss, ghost_rdc, 'SS', [TT('SOUS-SOLS · souterrains'), ('Sous-sol B015', -980, 1866.5, 30), ('Sous-sol B020', -951.5, 1859.5, 30), ('Sous-sol B035', -1066, 1866.0, 30)])
    render(r1, ghost_rdc, 'R1', [TT('R+1')])
    render(r2, [o for o in r1 if o[0] == 'L'] + ghost_rdc, 'R2', [TT('R+2'), ('R+2 · B020', -951.7, 1887.4, 30)])
