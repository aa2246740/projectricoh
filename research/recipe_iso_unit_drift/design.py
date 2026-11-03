"""Q1/Q4 design view: per unit, what each g137 recipe does to brightness/chroma relative to that unit's own 04 (model, ISO-independent rows)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
mods = g137_modules()
UNIT = {'50mm': 'jlaunch', '28mm': 'qlaunch', 'mount': 'l08firm'}
SLOTS = ('01', '02', '03', '05', '06', '07', '08')
models = {}
for u, n in UNIT.items():
    m = UnitModel(u, iso=200); m.base.entries = entries448(mods[n]); models[u] = m


def predict(m, slot, x):
    if slot == '03':
        r = m.mm.MatrixRow.from_bytes(m.base.entries['03']['written'][3][:28])
        return np.clip(np.repeat(r.apply(m.pre('03', x))[0][:, None], 3, 1), 0, 255)
    return m.predict(slot, x)


lab = lambda m, rgb: m.fs.lab_from_codes(np.asarray(rgb, float))
ramp = np.repeat(np.geomspace(20, 4000, 400)[:, None], 3, 1)
street = np.load(LOCAL / 'samples/R8051533.npz')['x']
out = {}
for u, m in models.items():
    L04 = lab(m, predict(m, '04', ramp))[:, 0]
    d = {}
    for target in (30, 50, 70):
        i = int(np.argmin(abs(L04 - target)))
        d[f'grey_L04_{target}'] = {s: float(lab(m, predict(m, s, ramp[i:i + 1]))[0, 0] - L04[i]) for s in SLOTS}
    S4 = lab(m, predict(m, '04', street))
    d['street1533_input'] = {s: dict(dL_median=float(np.median(lab(m, predict(m, s, street))[:, 0] - S4[:, 0])),
                                     chroma_ratio=float(np.median(np.hypot(*lab(m, predict(m, s, street))[:, 1:].T)) / np.median(np.hypot(*S4[:, 1:].T))))
                             for s in SLOTS}
    out[u] = d
dump(LOCAL / 'design_offsets.json', out)
for u in out:
    print(u)
    for k, v in out[u].items():
        print('  ', k, {s: (round(x, 1) if isinstance(x, float) else {a: round(b, 2) for a, b in x.items()}) for s, x in v.items()})
