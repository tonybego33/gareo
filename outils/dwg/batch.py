import sys, glob, pickle, time
sys.path.insert(0, '/home/claude/tools')
from dwg import *
from render import bbox
KEEP = lambda ln: ln == 'DEFPOINTS' or (ln.startswith('AREP_') and ln != 'AREP_Fond de plan')
res = {}
for f in sorted(glob.glob('/home/claude/in/toulon/*.dwg')):
    k = f.split('_', 1)[1][:-4] if False else f.split('/')[-1][8:-4]
    t = time.time(); D = Doc(f); F = Flat(D); P = F.run(skip_layers=KEEP)
    err = sum(1 for r in D.cache.values() if 'err' in r)
    from collections import Counter
    lays = Counter(o[1] for o in P)
    res[k] = P
    bb = bbox(P, 0.002) if P else None
    print(k, 'obj', len(D.cache), 'err', err, 'prims', len(P), 'bb', [round(x) for x in bb] if bb else None, dict(lays.most_common(4)), round(time.time()-t,1), flush=True)
pickle.dump(res, open('/home/claude/in/prims.pkl', 'wb'))
