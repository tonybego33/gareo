"""Lecteur DWG minimal (R2004+ / AC1018..AC1032), d'après la spec ODA.
Sections, décompression, carte des handles, objets graphiques simples."""
import struct, sys

# ---------------------------------------------------------------- conteneur
def lcg_bytes(n, seed=1):
    out = bytearray()
    for _ in range(n):
        seed = (seed * 0x343fd + 0x269ec3) & 0xffffffff
        out.append((seed >> 16) & 0xff)
    return out

def decompress(src, outsize):
    dst = bytearray(); i = 0; n = len(src)
    def rc():
        nonlocal i
        b = src[i]; i += 1; return b
    def lit_len():
        b = rc()
        if 0x01 <= b <= 0x0F: return b + 3, 0
        if b == 0:
            t = 0x0F
            while True:
                b = rc()
                if b: break
                t += 0xFF
            return t + b + 3, 0
        return 0, b                      # b est un opcode
    def long_off():
        b = rc(); t = 0
        if b == 0:
            t = 0xFF
            while True:
                b = rc()
                if b: break
                t += 0xFF
        return t + b
    def two_off():
        a = rc(); b = rc()
        return (a >> 2) | (b << 6), a & 3
    L, op = lit_len()
    dst += src[i:i+L]; i += L
    while i < n:
        if op == 0: op = rc()
        if op >= 0x40:
            cb = ((op & 0xF0) >> 4) - 1
            o2 = rc(); co = (o2 << 2) | ((op & 0x0C) >> 2)
            if op & 3: L = op & 3; op = 0
            else: L, op = lit_len()
        elif 0x21 <= op <= 0x3F:
            cb = op - 0x1E; co, L = two_off()
            if L: op = 0
            else: L, op = lit_len()
        elif op == 0x20:
            cb = long_off() + 0x21; co, L = two_off()
            if L: op = 0
            else: L, op = lit_len()
        elif 0x12 <= op <= 0x1F:
            cb = (op & 0x0F) + 2; co, L = two_off(); co += 0x3FFF
            if L: op = 0
            else: L, op = lit_len()
        elif op == 0x10:
            cb = long_off() + 9; co, L = two_off(); co += 0x3FFF
            if L: op = 0
            else: L, op = lit_len()
        elif op == 0x11:
            break
        else:
            raise ValueError('opcode %x @%d' % (op, i))
        s = len(dst) - co - 1
        if s < 0: raise ValueError('offset hors bornes')
        for k in range(cb): dst.append(dst[s + k])
        dst += src[i:i+L]; i += L
    return bytes(dst[:outsize])

class DWG:
    def __init__(self, path):
        self.b = open(path, 'rb').read()
        self.ver = self.b[:6].decode()
        h = bytes(x ^ y for x, y in zip(self.b[0x80:0x80+0x6c], lcg_bytes(0x6c)))
        assert h[:11] == b'AcFssFcAJMB', h[:12]
        self.hdr = h
        u = lambda o: struct.unpack_from('<I', h, o)[0]
        self.pmap_addr = struct.unpack_from('<Q', h, 0x54)[0] + 0x100
        self.smap_id = u(0x5C)
        self.pages = self._page_map()
        self.sections = self._section_map()

    def _sys_page(self, addr):
        typ, dsize, csize, ctype, _ = struct.unpack_from('<5I', self.b, addr)
        data = self.b[addr+20: addr+20+csize]
        return typ, (decompress(data, dsize) if ctype == 2 else data[:dsize])

    def _page_map(self):
        typ, d = self._sys_page(self.pmap_addr)
        assert typ == 0x41630e3b, hex(typ)
        pages = {}; addr = 0x100; o = 0
        while o + 8 <= len(d):
            num, size = struct.unpack_from('<iI', d, o); o += 8
            if num >= 0: pages[num] = (addr, size)
            else: o += 16
            addr += size
        return pages

    def _section_map(self):
        addr = self.pages[self.smap_id][0]
        typ, d = self._sys_page(addr)
        assert typ == 0x4163003b, hex(typ)
        ndesc = struct.unpack_from('<I', d, 0)[0]; o = 20; secs = {}
        for _ in range(ndesc):
            size, npg, maxs, _u, comp, sid, enc = struct.unpack_from('<QIIIIII', d, o); o += 32
            name = d[o:o+64].split(b'\0')[0].decode('latin1'); o += 64
            pgs = []
            for _ in range(npg):
                pn, dsz, start = struct.unpack_from('<IIQ', d, o); o += 16
                pgs.append((pn, dsz, start))
            secs[name] = dict(size=size, comp=comp, enc=enc, maxs=maxs, pages=pgs)
        return secs

    def section(self, name):
        s = self.sections[name]
        out = bytearray(s['size'])
        for pn, dsz, start in s['pages']:
            addr = self.pages[pn][0]
            mask = 0x4164536b ^ addr
            hd = struct.unpack_from('<8I', self.b, addr)
            hd = [x ^ mask for x in hd]
            csize, psize, poff = hd[2], hd[3], hd[4]
            raw = self.b[addr+32: addr+32+csize]
            data = decompress(raw, s['maxs']) if s['comp'] == 2 else raw
            n = min(len(data), s['size'] - poff)
            out[poff:poff+n] = data[:n]
        return bytes(out)

if __name__ == '__main__':
    d = DWG(sys.argv[1])
    print(d.ver, hex(d.pmap_addr), len(d.pages))
    for k, v in d.sections.items():
        print(repr(k), v['size'], v['comp'], v['enc'], len(v['pages']))

# ---------------------------------------------------------------- bits
class Bits:
    def __init__(self, data, pos=0, end=None):
        self.d = data; self.p = pos; self.end = end if end is not None else len(data) * 8
        self.strs = None
    def b(self):
        v = (self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1; self.p += 1; return v
    def bits(self, n):
        v = 0
        for _ in range(n): v = (v << 1) | self.b()
        return v
    def rc(self):
        if self.p & 7 == 0:
            v = self.d[self.p >> 3]; self.p += 8; return v
        return self.bits(8)
    def raw(self, n): return bytes(self.rc() for _ in range(n))
    def rs(self): return struct.unpack('<H', self.raw(2))[0]
    def rl(self): return struct.unpack('<I', self.raw(4))[0]
    def rd(self): return struct.unpack('<d', self.raw(8))[0]
    def bb(self): return self.bits(2)
    def bs(self):
        c = self.bb()
        return [self.rs, self.rc, lambda: 0, lambda: 256][c]()
    def bl(self):
        c = self.bb()
        if c == 0: return self.rl()
        if c == 1: return self.rc()
        return 0
    def bll(self):
        n = self.bits(3); v = 0
        for i in range(n): v |= self.rc() << (8 * i)
        return v
    def bd(self):
        c = self.bb()
        if c == 0: return self.rd()
        if c == 1: return 1.0
        if c == 2: return 0.0
        raise ValueError('BD 3')
    def dd(self, dflt):
        c = self.bb()
        if c == 0: return dflt
        if c == 3: return self.rd()
        bb = bytearray(struct.pack('<d', dflt))
        if c == 1: bb[0:4] = self.raw(4)
        else:
            bb[4:6] = self.raw(2); bb[0:4] = self.raw(4)
        return struct.unpack('<d', bytes(bb))[0]
    def bt(self): return 0.0 if self.b() else self.bd()
    def be(self):
        if self.b(): return (0.0, 0.0, 1.0)
        return (self.bd(), self.bd(), self.bd())
    def p3bd(self): return (self.bd(), self.bd(), self.bd())
    def p2rd(self): return (self.rd(), self.rd())
    def h(self, ref=0):
        code = self.bits(4); n = self.bits(4); v = 0
        for _ in range(n): v = (v << 8) | self.rc()
        if code == 6: return ref + 1
        if code == 8: return ref - 1
        if code == 0xA: return ref + v
        if code == 0xC: return ref - v
        return v
    def hraw(self):
        code = self.bits(4); n = self.bits(4); v = 0
        for _ in range(n): v = (v << 8) | self.rc()
        return code, v
    def bot(self):
        c = self.bb()
        if c == 0: return self.rc()
        if c == 1: return self.rc() + 0x1F0
        return self.rs()
    def tu(self):
        n = self.bs()
        return self.raw(2 * n).decode('utf-16le', 'replace').rstrip('\0')
    def tv(self):
        return self.strs.tu() if self.strs else ''
    def enc(self):
        v = self.bs(); fl = v >> 8; idx = v & 0x1ff; rgb = None
        if fl & 0x80: rgb = self.bl()
        if fl & 0x20: self.bl()
        return idx, rgb, fl

def mc_u(d, o):
    v = 0; sh = 0
    while True:
        b = d[o]; o += 1
        v |= (b & 0x7f) << sh; sh += 7
        if not b & 0x80: return v, o
def mc_s(d, o):
    v = 0; sh = 0
    while True:
        b = d[o]; o += 1
        if b & 0x80:
            v |= (b & 0x7f) << sh; sh += 7
        else:
            v |= (b & 0x3f) << sh
            return (-v if b & 0x40 else v), o
def ms(d, o):
    v = 0; sh = 0
    while True:
        w = d[o] | (d[o+1] << 8); o += 2
        v |= (w & 0x7fff) << sh; sh += 15
        if not w & 0x8000: return v, o

def handle_map(data):
    o = 0; m = {}; h = 0; loc = 0
    while o < len(data):
        size = (data[o] << 8) | data[o+1]
        if size <= 2: break
        end = o + size; o += 2; h = 0; loc = 0
        while o < end:
            dh, o = mc_u(data, o); dl, o = mc_s(data, o)
            h += dh; loc += dl; m[h] = loc
        o = end + 2
    return m

# ---------------------------------------------------------------- objets
ENT_TYPES = {1:'TEXT',2:'ATTRIB',3:'ATTDEF',4:'BLOCK',5:'ENDBLK',6:'SEQEND',7:'INSERT',8:'MINSERT',
             10:'VERTEX_2D',15:'POLYLINE_2D',17:'ARC',18:'CIRCLE',19:'LINE',31:'SOLID',34:'VIEWPORT',
             35:'ELLIPSE',36:'SPLINE',44:'MTEXT',77:'LWPOLYLINE',78:'HATCH',
             20:'DIM_ORD',21:'DIM_LIN',22:'DIM_ALIGNED',23:'DIM_ANG3',24:'DIM_ANG2',25:'DIM_RAD',26:'DIM_DIAM',
             27:'POINT',28:'3DFACE',41:'RAY',40:'XLINE',45:'LEADER',47:'MLINE',37:'REGION',38:'3DSOLID',30:'POLYLINE_3D',11:'VERTEX_3D'}

class Doc:
    def __init__(self, path):
        self.f = DWG(path)
        self.ob = self.f.section('AcDb:AcDbObjects')
        self.hm = handle_map(self.f.section('AcDb:Handles'))
        self.cache = {}

    def stream(self, h):
        loc = self.hm[h]; ob = self.ob
        size, o = ms(ob, loc); hs, o2 = mc_u(ob, o)
        base = o2 * 8                     # début des données (après MC)
        bitsize = size * 8 - hs
        dat = Bits(ob, o2 * 8, base + bitsize)
        hdl = Bits(ob, base + bitsize, base + size * 8)
        # flux de chaînes (R2007+)
        endb = base + bitsize - 1
        sb = Bits(ob, endb)
        if sb.b():
            p = endb - 16; sb.p = p; n = sb.rs()
            if n & 0x8000:
                p -= 16; sb.p = p; hi = sb.rs(); n = (n & 0x7fff) | (hi << 15)
            dat.strs = Bits(ob, p - n)
        return dat, hdl

    def obj(self, h):
        if h in self.cache: return self.cache[h]
        try: r = self._obj(h)
        except Exception as e: r = {'h': h, 'type': -1, 'err': repr(e)}
        self.cache[h] = r; return r

    def _obj(self, h):
        d, hd = self.stream(h)
        t = d.bot(); hh = d.h()
        while True:                       # EED
            n = d.bs()
            if not n: break
            d.h(); d.p += 8 * n
        r = {'h': h, 'type': t}
        if t in ENT_TYPES:
            r['name'] = ENT_TYPES[t]
            if d.b():
                n = d.bll(); d.p += 8 * n
            em = d.bb(); nreac = d.bl(); xdm = d.b(); d.b()       # has ds data (R2013+)
            col = d.enc(); d.bd(); ltf = d.bb(); psf = d.bb(); mtf = d.bb(); d.rc()
            fvs = d.b(); fcs = d.b(); egs = d.b(); d.bs(); d.rc()
            r['color'] = col[0]; r['rgb'] = col[1]
            # handles communs
            r['owner'] = hd.h(h) if em == 0 else None
            r['entmode'] = em
            for _ in range(nreac): hd.h(h)
            if not xdm: hd.h(h)
            if col[2] & 0x40: hd.h(h)
            r['layer'] = hd.h(h)
            if ltf == 3: hd.h(h)
            if mtf == 3: hd.h(h)
            if psf == 3: hd.h(h)
            if fvs: hd.h(h)
            if fcs: hd.h(h)
            if egs: hd.h(h)
            self._ent(t, d, hd, r, h)
        else:
            nreac = d.bl(); xdm = d.b(); d.b()
            if t == 51:                    # LAYER
                r['name'] = 'LAYER'; r['lname'] = d.tv()
                fl = d.bs(); r['frozen'] = bool(fl & 1); r['off'] = False
                c = d.bs(); r['off'] = c >= 0x8000 if False else None
            elif t == 49:                  # BLOCK_HEADER
                r['name'] = 'BLOCK_HEADER'; r['bname'] = d.tv()
                d.b(); d.b(); r['anon'] = d.b(); hasatt = d.b(); isx = d.b(); d.b(); d.b()
                n_owned = d.bl()
                r['base'] = d.p3bd()
        return r

    def _ent(self, t, d, hd, r, h):
        if t == 19:
            zz = d.b(); x1 = d.rd(); x2 = d.dd(x1); y1 = d.rd(); y2 = d.dd(y1)
            r['pts'] = [(x1, y1), (x2, y2)]
        elif t == 77:
            fl = d.bs()
            if fl & 4: d.bd()
            if fl & 8: d.bd()
            if fl & 2: d.bd()
            if fl & 1: d.p3bd()
            npt = d.bl(); nb = d.bl() if fl & 16 else 0
            nid = d.bl() if fl & 1024 else 0
            nw = d.bl() if fl & 32 else 0
            if npt > 100000: raise ValueError('npt')
            pts = []
            if npt:
                x, y = d.rd(), d.rd(); pts.append((x, y))
                for _ in range(npt - 1):
                    x = d.dd(x); y = d.dd(y); pts.append((x, y))
            bul = [d.bd() for _ in range(nb)]
            r['pts'] = pts; r['closed'] = bool(fl & 512); r['bulges'] = bul
        elif t in (17, 18):
            c = d.p3bd(); rad = d.bd(); d.bt(); d.be()
            r['c'] = c[:2]; r['r'] = rad
            if t == 17: r['a0'] = d.bd(); r['a1'] = d.bd()
        elif t in (1, 2, 3):
            df = d.rc()
            if not df & 1: d.rd()
            ins = d.p2rd(); r['ins'] = ins
            if not df & 2: r['al'] = (d.dd(ins[0]), d.dd(ins[1]))
            d.be(); d.bt()
            if not df & 4: d.rd()
            r['rot'] = 0.0 if df & 8 else d.rd()
            r['ht'] = d.rd()
            if not df & 0x10: d.rd()
            r['text'] = d.tv()
            if not df & 0x20: d.bs()
            r['ha'] = 0 if df & 0x40 else d.bs()
            r['va'] = 0 if df & 0x80 else d.bs()
            if t == 2 or t == 3:
                d.rc()                       # version R2010+
                at = d.rc()                  # type R2018+
                if at == 1:
                    r['tag'] = d.tv()
        elif t == 44:
            ins = d.p3bd(); d.p3bd(); xd = d.p3bd(); w = d.bd(); d.bd(); ht = d.bd()
            att = d.bs(); d.bs(); d.bd(); d.bd()
            r['ins'] = ins[:2]; r['xdir'] = xd[:2]; r['ht'] = ht; r['att'] = att; r['w'] = w
            r['text'] = d.tv()
        elif t == 15:                                  # POLYLINE_2D
            fl = d.bs(); d.bs(); d.bd(); d.bd(); d.bt(); d.bd(); d.be(); d.bl()
            r['closed'] = bool(fl & 1)
        elif t == 10:                                  # VERTEX_2D
            fl = d.rc(); p = d.p3bd(); sw = d.bd()
            if sw >= 0: d.bd()
            r['bulge'] = d.bd(); r['pt'] = p[:2]; r['vflags'] = fl
        elif t == 7 or t == 8:
            ins = d.p3bd(); fl = d.bb()
            if fl == 3: sc = (1.0, 1.0)
            elif fl == 1: sx = 1.0; sy = d.dd(sx); d.dd(sx); sc = (sx, sy)
            elif fl == 2: sx = d.rd(); sc = (sx, sx)
            else: sx = d.rd(); sy = d.dd(sx); d.dd(sx); sc = (sx, sy)
            rot = d.bd(); ext = d.be() if False else d.p3bd(); hasatt = d.b()
            if t == 8: d.bs(); d.bs(); d.bd(); d.bd()
            r['ins'] = ins[:2]; r['sc'] = sc; r['rot'] = rot; r['ext'] = ext
            r['block'] = hd.h(h)


# ---------------------------------------------------------------- géométrie
import math
def mat_insert(ins, sc, rot, base):
    c, s_ = math.cos(rot), math.sin(rot)
    a, b, cc, dd = c*sc[0], -s_*sc[1], s_*sc[0], c*sc[1]
    tx = ins[0] - (a*base[0] + b*base[1]); ty = ins[1] - (cc*base[0] + dd*base[1])
    return (a, b, cc, dd, tx, ty)
def mmul(m, n):   # m∘n
    a,b,c,d,e,f = m; A,B,C,D,E,F = n
    return (a*A+b*C, a*B+b*D, c*A+d*C, c*B+d*D, a*E+b*F+e, c*E+d*F+f)
def ap(m, p): return (m[0]*p[0]+m[1]*p[1]+m[4], m[2]*p[0]+m[3]*p[1]+m[5])
IDM = (1,0,0,1,0,0)

def arc_pts(c, r, a0, a1, n=None):
    while a1 <= a0: a1 += 2*math.pi
    n = n or max(4, int((a1-a0)/(math.pi/18)))
    return [(c[0]+r*math.cos(a0+(a1-a0)*i/n), c[1]+r*math.sin(a0+(a1-a0)*i/n)) for i in range(n+1)]

def bulge_pts(pts, bul, closed):
    out = []; n = len(pts)
    segs = n if closed else n-1
    for i in range(segs):
        p, q = pts[i], pts[(i+1) % n]; b = bul[i] if i < len(bul) else 0
        out.append(p)
        if abs(b) > 1e-9:
            th = 4*math.atan(b); dx, dy = q[0]-p[0], q[1]-p[1]; L = math.hypot(dx, dy)
            if L > 0:
                r = L/(2*math.sin(th/2)); mx, my = (p[0]+q[0])/2, (p[1]+q[1])/2
                h = r*math.cos(th/2); nx, ny = -dy/L, dx/L
                cx, cy = mx + nx*h, my + ny*h
                a0 = math.atan2(p[1]-cy, p[0]-cx); 
                for k in range(1, 8):
                    a = a0 + th*k/8
                    out.append((cx + abs(r)*math.cos(a) if r>0 else cx + abs(r)*math.cos(a), cy + abs(r)*math.sin(a)))
    out.append(pts[-1] if not closed else pts[0])
    return out

class Flat:
    """Aplatissement de l'espace objet : liste de primitives en coordonnées monde."""
    def __init__(self, doc):
        self.D = doc
        for h in doc.hm: doc.obj(h)
        self.layers = {h: r['lname'] for h, r in doc.cache.items() if r.get('name') == 'LAYER'}
        self.blocks = {h: r for h, r in doc.cache.items() if r.get('name') == 'BLOCK_HEADER'}
        self.owned = {}
        self.ms = []
        for h, r in sorted(doc.cache.items()):
            if r.get('name') not in ENT_TYPES.values(): continue
            if r.get('entmode') == 2: self.ms.append(r)
            elif r.get('entmode') == 0: self.owned.setdefault(r['owner'], []).append(r)
    def run(self, skip_layers=lambda n: False, maxdepth=8):
        out = []
        self._walk(self.ms, IDM, None, out, skip_layers, 0, maxdepth)
        return out
    def _walk(self, ents, M, parent_layer, out, skip, depth, maxdepth):
        for r in ents:
            ln = self.layers.get(r.get('layer'), '?')
            if ln == '0' and parent_layer: ln = parent_layer
            if skip(ln): continue
            n = r['name']
            if n == 'LINE':
                out.append(('L', ln, [ap(M, p) for p in r['pts']], r))
            elif n == 'LWPOLYLINE':
                pts = r['pts']
                if len(pts) >= 2:
                    pp = bulge_pts(pts, r.get('bulges', []), r['closed']) if r.get('bulges') else (pts + ([pts[0]] if r['closed'] else []))
                    out.append(('L', ln, [ap(M, p) for p in pp], r))
            elif n == 'POLYLINE_2D':
                vs = [v for v in self.owned.get(r['h'], []) if v['name'] == 'VERTEX_2D' and not v.get('vflags', 0) & 16]
                pts = [v['pt'] for v in vs]
                if len(pts) >= 2:
                    pp = bulge_pts(pts, [v.get('bulge', 0) for v in vs], r.get('closed'))
                    out.append(('L', ln, [ap(M, p) for p in pp], r))
            elif n == 'CIRCLE':
                out.append(('L', ln, [ap(M, p) for p in arc_pts(r['c'], r['r'], 0, 2*math.pi, 36)], r))
            elif n == 'ARC':
                out.append(('L', ln, [ap(M, p) for p in arc_pts(r['c'], r['r'], r['a0'], r['a1'])], r))
            elif n in ('TEXT', 'ATTRIB', 'MTEXT'):
                if r.get('text'):
                    p = r['al'] if n != 'MTEXT' and (r.get('ha') or r.get('va')) and r.get('al') else r['ins']
                    sc = math.hypot(M[0], M[2])
                    rot = r.get('rot', 0.0) if n != 'MTEXT' else math.atan2(r['xdir'][1], r['xdir'][0])
                    rot += math.atan2(M[2], M[0])
                    out.append(('T', ln, ap(M, p), r['text'], r['ht']*sc, rot, r))
            elif n in ('INSERT', 'MINSERT') and depth < maxdepth:
                b = self.blocks.get(r['block'])
                if not b: continue
                if r.get('ext', (0,0,1))[2] < 0:
                    sc = (-r['sc'][0], r['sc'][1]); rot = math.pi - r['rot']
                else: sc = r['sc']; rot = r['rot']
                M2 = mmul(M, mat_insert(r['ins'], sc, rot, b['base']))
                self._walk(self.owned.get(r['block'], []), M2, ln, out, skip, depth+1, maxdepth)
                self._walk(self.owned.get(r['h'], []), M, ln, out, skip, depth+1, maxdepth)   # ATTRIB
        return out
