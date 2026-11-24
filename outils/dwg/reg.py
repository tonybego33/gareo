import sys, pickle, math
sys.path.insert(0, '/home/claude/tools')
import numpy as np
from render import main_bbox
R = pickle.load(open('/home/claude/in/prims.pkl', 'rb'))
def segs(P, bb=None):
    out = []
    for o in P:
        if o[0] != 'L': continue
        pts = o[2]
        for a, b in zip(pts, pts[1:]):
            if bb and not (bb[0] <= a[0] <= bb[2] and bb[1] <= a[1] <= bb[3]): continue
            out.append((a, b))
    return out
def dom_angle(S):
    h = np.zeros(900)
    for a, b in S:
        L = math.hypot(b[0]-a[0], b[1]-a[1])
        if L < 0.5: continue
        ang = math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])) % 90
        h[int(ang*10) % 900] += L
    h = np.convolve(np.r_[h[-5:], h, h[:5]], np.ones(11), 'valid')
    return np.argmax(h) / 10
def endpoints(S, minlen=1.0):
    pts = []
    for a, b in S:
        if math.hypot(b[0]-a[0], b[1]-a[1]) >= minlen: pts += [a, b]
    return np.unique(np.round(np.array(pts), 2), axis=0)
if __name__ == '__main__':
  rdc = []
  for k in ['014_00', '015_00', '020_00', '035_00', '037_00']: rdc += R[k]
  SR = segs(rdc, main_bbox(R['020_00']))
  ER = endpoints(SR)
  print('RDC angle', dom_angle(SR), 'endpoints', len(ER))
  res = {}
  for k in ['015_s1', '020_s1', '035_s1']:
      bb = main_bbox(R[k]); S = segs(R[k], bb)
      a = dom_angle(S); print(k, 'angle', a)
      best = None
      for base in [a, a+90, a+180, a+270]:
          th = math.radians(-base)
          c, s = math.cos(th), math.sin(th)
          E = endpoints(S)
          E2 = np.c_[E[:, 0]*c - E[:, 1]*s, E[:, 0]*s + E[:, 1]*c]
          rng = np.random.default_rng(0)
          samp = E2[rng.choice(len(E2), min(400, len(E2)), replace=False)]
          D = (ER[None, :, :] - samp[:, None, :]).reshape(-1, 2)
          q = np.round(D / 0.05).astype(np.int64)
          key = q[:, 0] * 10**7 + q[:, 1]
          u, cnt = np.unique(key, return_counts=True)
          i = np.argmax(cnt); top = np.sort(cnt)[-3:]
          tx = (u[i] // 10**7) * 0.05 if u[i] >= 0 else -((-u[i]) // 10**7) * 0.05
          # décodage robuste
          qx = int(np.round(u[i] / 10**7)); qy = int(u[i] - qx * 10**7)
          t = (qx*0.05, qy*0.05)
          print('  rot', round(base, 1), 'votes', top, 't', t)
          if not best or cnt[i] > best[0]: best = (int(cnt[i]), base, t)
      res[k] = best
  pickle.dump(res, open('/home/claude/in/reg.pkl', 'wb'))
  print(res)
