"""Q2b: MOUNT 04 vs 50mm 04 for the SAME calibrated input (exposure-matched): what is left after removing the chart exposure offset."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
mods = g137_modules()
res = {}
mods_m = {u: UnitModel(u, iso=200) for u in ('50mm', 'mount', '28mm')}
for u, n in (('50mm', 'jlaunch'), ('mount', 'l08firm'), ('28mm', 'qlaunch')):
    mods_m[u].base.entries = entries448(mods[n])
lab = lambda m, r: m.fs.lab_from_codes(np.asarray(r, float))
rng = np.random.default_rng(1)
inputs = {'street1533': np.load(LOCAL / 'samples/R8051533.npz')['x'],
          'street1577': np.load(LOCAL / 'samples/R8051577.npz')['x'],
          'random_rgb': rng.uniform(80, 3000, (3000, 3))}
for name, x in inputs.items():
    a = lab(mods_m['mount'], mods_m['mount'].predict('04', x)); b = lab(mods_m['50mm'], mods_m['50mm'].predict('04', x)); c = lab(mods_m['28mm'], mods_m['28mm'].predict('04', x))
    res[name] = dict(n=len(x), mount_vs_50mm=dict(dE_med=float(np.median(mods_m['mount'].fs.delta_e00(a, b))), dE_p90=float(np.percentile(mods_m['mount'].fs.delta_e00(a, b), 90)),
                                                  dL_med=float(np.median(a[:, 0] - b[:, 0])), dC_med=float(np.median(np.hypot(*a[:, 1:].T) - np.hypot(*b[:, 1:].T)))),
                     r28_vs_50mm=dict(dE_med=float(np.median(mods_m['mount'].fs.delta_e00(c, b))), dL_med=float(np.median(c[:, 0] - b[:, 0]))))
dump(LOCAL / 'q2_stock_diff.json', res); print(json.dumps(res, indent=1))
