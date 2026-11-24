import math
def xf_prims(P, rot, tx, ty):
    th = math.radians(rot); c, s = math.cos(th), math.sin(th)
    f = lambda p: (p[0]*c - p[1]*s + tx, p[0]*s + p[1]*c + ty)
    out = []
    for o in P:
        if o[0] == 'L': out.append(('L', o[1], [f(p) for p in o[2]]) + o[3:])
        else: out.append(('T', o[1], f(o[2]), o[3], o[4], o[5] + th) + o[6:])
    return out
