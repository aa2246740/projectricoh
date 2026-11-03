"""Q5: predicted effect of candidate MOUNT fixes on the 1533 street input (MOUNT model, ISO-independent rows).

current  = g137 MOUNT rows (camera-verified at ISO 800 by score_frames.py)
A_shift  = MOUNT rows with tone input nodes divided by k = 2^dEV (undo the chart exposure anchor), colour rows untouched
C_50mm   = 50mm g137 rows run on MOUNT (what 28mm already does)
Reference for 01/02: the GR IV 17^3 model render of R8051533 (research/gr_posneg_gap), sampled at the same grid points.
"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
import struct
dEV = json.loads((LOCAL / 'q2_anchor.json').read_text())['raw_green_EV_mount_minus_50mm']
k = 2 ** dEV
mods = g137_modules()
cur = entries448(mods['l08firm']); mm50 = entries448(mods['jlaunch'])
SLOTS = ('01', '02', '03', '05', '06', '07', '08')


def shifted(entries):
    out = {}
    for s, e in entries.items():
        e = dict(e)
        if s != '04':
            a = list(struct.unpack('>31H', e['written'][0]))
            na = [int(round(v / k)) for v in a]
            for i in range(1, 31):  # keep strictly increasing
                na[i] = max(na[i], na[i - 1] + 1)
            w = list(e['written']); w[0] = struct.pack('>31H', *na); e['written'] = tuple(w)
        out[s] = e
    return out


VARIANTS = {'current': cur, 'A_shift': shifted(cur), 'C_50mm': {**mm50, '04': cur['04']}}
M = UnitModel('mount', iso=200)


def predict(slot, x):
    if slot == '03':
        r = M.mm.MatrixRow.from_bytes(M.base.entries['03']['written'][3][:28])
        return np.clip(np.repeat(r.apply(M.pre('03', x))[0][:, None], 3, 1), 0, 255)
    return M.predict(slot, x)


lab = lambda rgb: M.fs.lab_from_codes(np.asarray(rgb, float))
a = np.load(LOCAL / 'samples/R8051533.npz'); x = a['x']; c = a['centers']; obs04 = lab(a['jpeg'])
ref = {}
for slot, name in (('01', 'pos'), ('02', 'neg')):
    im = np.asarray(Image.open(ROOT / f'captures/gr-posneg-gap/R8051533_04_to_GRIV_{name}_model17.jpg').convert('RGB'), float)
    assert im.shape[1] == a['size'][0] and im.shape[0] == a['size'][1]
    dx, dy = np.meshgrid(np.arange(-6, 6), np.arange(-6, 6))
    ref[slot] = lab(im[c[:, 1, None] + dy.ravel(), c[:, 0, None] + dx.ravel()].mean(1))
grey = np.hypot(*obs04[:, 1:].T) < 8
res = {'dEV': dEV, 'k': k, 'n': len(x), 'n_grey': int(grey.sum())}
for vname, ents in VARIANTS.items():
    M.base.entries = ents
    p4 = lab(predict('04', x)); r = {}
    for s in SLOTS:
        p = lab(predict(s, x))
        d = dict(dL_vs_04=float(np.median(p[:, 0] - p4[:, 0])), dL_vs_04_grey=float(np.median(p[grey, 0] - p4[grey, 0])),
                 highlight_p95_L=float(np.percentile(p[:, 0], 95)))
        if s in ref:
            e = M.fs.delta_e00(p, ref[s]); b = M.fs.delta_e00(obs04, ref[s])
            d.update(dE_to_GRIV=float(np.median(e)), dE_04_to_GRIV=float(np.median(b)), similarity=float(1 - np.median(e) / np.median(b)),
                     dL_to_GRIV=float(np.median(p[:, 0] - ref[s][:, 0])))
        r[s] = d
    res[vname] = r
res['GRIV_ref_dL_vs_04'] = {s: float(np.median(ref[s][:, 0] - obs04[:, 0])) for s in ref}
dump(LOCAL / 'q5_fixes.json', res)
print('dEV', round(dEV, 3), 'GRIV ref dL vs 04', {s: round(v, 2) for s, v in res['GRIV_ref_dL_vs_04'].items()})
for v in VARIANTS:
    print(v)
    for s, d in res[v].items():
        print('   ', s, {kk: round(vv, 2) for kk, vv in d.items()})

# warm/red hue offsets vs the GR IV reference (the user-visible 'red/orange toward magenta' symptom)
warm = {}
h = lambda L: np.degrees(np.arctan2(L[:, 2], L[:, 1])) % 360
for slot in ('01', '02'):
    hr = h(ref[slot]); cr = np.hypot(*ref[slot][:, 1:].T)
    sel = (cr > 12) & ((hr < 75) | (hr > 345))
    warm[slot] = {'n': int(sel.sum())}
    for vname, ents in VARIANTS.items():
        M.base.entries = ents
        p = lab(predict(slot, x))
        dh = (h(p)[sel] - hr[sel] + 180) % 360 - 180
        warm[slot][vname] = dict(dhue_med=float(np.median(dh)), chroma_ratio=float(np.median(np.hypot(*p[sel, 1:].T)) / np.median(cr[sel])))
res['warm_hue'] = warm
dump(LOCAL / 'q5_fixes.json', res)
print(json.dumps(warm, indent=1))
