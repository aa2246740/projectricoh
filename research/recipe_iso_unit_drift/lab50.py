"""Recheck the earlier '50mm 01 mid-grey only -0.3 vs 04' figure against the g137 50mm 01/02 rows on the same chart inputs."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
d = np.load(ROOT / 'research/gr4_dense_returns_r1/local/fit/data.npz')
mods = g137_modules()
m = UnitModel('50mm', iso=200); m.base.entries = entries448(mods['jlaunch'])
lab = lambda r: m.fs.lab_from_codes(np.asarray(r, float))
x = d['scene_x']; base = lab(d['base_rgb']); obs = lab(d['observed_rgb']); tgt = d['new_target']
if tgt.max() > 101: tgt = lab(tgt)
p4 = lab(m.predict('04', x)); p1 = lab(m.predict('01', x)); p2 = lab(m.predict('02', x))
g = np.hypot(*base[:, 1:].T) < 8
res = dict(n=len(x), n_grey=int(g.sum()), base_L_grey=float(np.median(base[g, 0])))
for name, L in (('observed_rgb', obs), ('new_target', tgt), ('g137_01', p1), ('g137_02', p2), ('model_04', p4)):
    res[name] = dict(dL_grey=float(np.median(L[g, 0] - base[g, 0])), dL_all=float(np.median(L[:, 0] - base[:, 0])))
dump(LOCAL / 'lab50_recheck.json', res); print(json.dumps(res, indent=1))
