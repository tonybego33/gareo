import sys, pickle, math
sys.path.insert(0, '/home/claude/tools')
import numpy as np
from render import main_bbox
from reg import segs, dom_angle, endpoints
R = pickle.load(open('/home/claude/in/prims.pkl', 'rb'))
RES = 0.1
def raster(S, bb, dil=2):
    W = int((bb[2]-bb[0])/RES)+1; H = int((bb[3]-bb[1])/RES)+1
    g = np.zeros((H, W), bool)
    for a, b in S:
        L = math.hypot(b[0]-a[0], b[1]-a[1]); n = max(2, int(L/RES*2))
        t = np.linspace(0, 1, n)
        x = ((a[0] + (b[0]-a[0])*t - bb[0])/RES).astype(int); y = ((a[1] + (b[1]-a[1])*t - bb[1])/RES).astype(int)
        m = (x >= 0) & (x < W) & (y >= 0) & (y < H); g[y[m], x[m]] = True
    from scipy.ndimage import binary_dilation
    return binary_dilation(g, iterations=dil)
def samples(S, step=0.3, minlen=1.0):
    pts = []
    for a, b in S:
        L = math.hypot(b[0]-a[0], b[1]-a[1])
        if L < minlen: continue
        n = int(L/step)+1
        for t in np.linspace(0, 1, n): pts.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t))
    return np.array(pts)
def register(k, refkeys, refbb, rots, margin=8):
    bb = main_bbox(R[k]); S = segs(R[k], bb)
    ref = []
    for rk in refkeys: ref += R[rk]
    rbb = (refbb[0]-margin, refbb[1]-margin, refbb[2]+margin, refbb[3]+margin)
    SR = segs(ref, rbb); ER = endpoints(SR, 0.5)
    G = raster(SR, rbb)
    P = samples(S); E = endpoints(S, 0.5)
    best = (0, None)
    for rot in rots:
        th = math.radians(rot); c, s = math.cos(th), math.sin(th)
        rotm = lambda A: np.c_[A[:, 0]*c - A[:, 1]*s, A[:, 0]*s + A[:, 1]*c]
        E2 = rotm(E); P2 = rotm(P)
        rng = np.random.default_rng(1)
        samp = E2[rng.choice(len(E2), min(300, len(E2)), replace=False)]
        D = (ER[None] - samp[:, None]).reshape(-1, 2)
        q = np.round(D/0.1).astype(np.int64)
        key = q[:, 0]*100000 + q[:, 1]
        u, cnt = np.unique(key, return_counts=True)
        order = np.argsort(-cnt)[:80]
        for i in order:
            qx = int(np.round(u[i]/100000)); qy = int(u[i]-qx*100000)
            t = np.array([qx*0.1, qy*0.1])
            Q = P2 + t
            x = ((Q[:, 0]-rbb[0])/RES).astype(int); y = ((Q[:, 1]-rbb[1])/RES).astype(int)
            m = (x >= 0) & (x < G.shape[1]) & (y >= 0) & (y < G.shape[0])
            sc = (G[y[m], x[m]].sum())/len(Q)
            if sc > best[0]: best = (sc, (rot, float(t[0]), float(t[1])))
    return best
if __name__ == '__main__':
  out = {}
  b = register('020_s1', ['020_00', '020_01', '020_02', '037_00'], (-962, 1862, -940, 1888), [0, 90, 180, 270])
  print('020_s1', b); out['020_s1'] = b
  b = register('015_s1', ['015_00', '020_00', '015_01'], (-1056, 1860, -962, 1894), [0, 90, 180, 270])
  print('015_s1', b); out['015_s1'] = b
  a = dom_angle(segs(R['035_s1'], main_bbox(R['035_s1'])))
  b = register('035_s1', ['035_00', '020_00'], (-1110, 1864, -1050, 1894), [ -a + d for d in (0, 90, 180, 270)])
  print('035_s1', a, b); out['035_s1'] = b
  pickle.dump(out, open('/home/claude/in/reg.pkl', 'wb'))
