"""How much the 50mm 06 depends on its C/D (T1) curves when run on MOUNT: with vs without the C/D rows (street input)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
mods = g137_modules(); e50 = entries448(mods['jlaunch']); cur = entries448(mods['l08firm'])
M = UnitModel('mount', iso=200)
lab = lambda r: M.fs.lab_from_codes(np.asarray(r, float))
res = {}
for f in ('R8051533', 'R8051577'):
    x = np.load(LOCAL / f'samples/{f}.npz')['x']
    M.base.entries = {**e50, '04': cur['04']}; withT1 = lab(M.predict('06', x)); p04 = lab(M.predict('04', x))
    noT = dict(e50['06']); noT['mask'] = 1; noT['control'] = 2
    M.base.entries = {**e50, '04': cur['04'], '06': noT}; without = lab(M.predict('06', x))
    d = M.fs.delta_e00(withT1, without)
    res[f] = dict(dE_med=float(np.median(d)), dE_p90=float(np.percentile(d, 90)), dL_med=float(np.median(without[:, 0] - withT1[:, 0])),
                  withT1_dL_vs_04=float(np.median(withT1[:, 0] - p04[:, 0])))
dump(LOCAL / 'q5_t1_check.json', res); print(res)
