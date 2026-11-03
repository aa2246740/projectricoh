"""Q2: how far the MOUNT 01/02 fit targets (built from the 50mm 04 chart renders) sit from MOUNT's own 04 renders of the same patches."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from mount_model import *
EX = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6'
M, _, _ = mount_model()
lab = lambda rgb: M.fs.lab_from_codes(np.asarray(rgb, float))


def rows(unit):
    fr = json.loads((EX / unit / 'frames.json').read_text())['frames']
    out = {}
    for line in (EX / unit / 'patches.jsonl').read_text().splitlines():
        r = json.loads(line)
        if r['valid'] and fr[r['frame']]['selector_bytes']['recipe_slot'] == '04':
            out[(r['page'], r['patch_id'])] = r
    return out, fr


m4, mf = rows('mount'); f4, ff = rows('50mm')
res = {}
keys = sorted(set(m4) & set(f4))
Lm = lab([m4[k]['jpeg_rgb'] for k in keys]); Lf = lab([f4[k]['jpeg_rgb'] for k in keys])
cm, cf = np.hypot(*Lm[:, 1:].T), np.hypot(*Lf[:, 1:].T)
grey = cf < 8
res['mount04_minus_50mm04'] = dict(n=len(keys), dL_median=float(np.median(Lm[:, 0] - Lf[:, 0])),
    dL_median_grey=float(np.median(Lm[grey, 0] - Lf[grey, 0])), n_grey=int(grey.sum()),
    dC_median=float(np.median(cm - cf)), dE00_median=float(np.median(M.fs.delta_e00(Lm, Lf))),
    dL_by_L50mm_bins={f'{a}-{b}': float(np.median((Lm[:, 0] - Lf[:, 0])[(Lf[:, 0] >= a) & (Lf[:, 0] < b)])) for a, b in ((0, 30), (30, 50), (50, 70), (70, 101)) if ((Lf[:, 0] >= a) & (Lf[:, 0] < b)).sum()})
res['exposure'] = dict(mount={k: [mf[k]['shutter_s'], mf[k]['aperture_f'], mf[k]['white_balance']['gains']] for k in list(mf)[:1]},
                       mm50={k: [ff[k]['shutter_s'], ff[k]['aperture_f'], ff[k]['white_balance']['gains']] for k in list(ff)[:1]})
# raw (pre-WB) green ratio for the same patches: exposure difference at the sensor
rg = np.array([m4[k]['raw_rgb'][1] / f4[k]['raw_rgb'][1] for k in keys])
ok = np.array([min(m4[k]['raw_rgb'][1], f4[k]['raw_rgb'][1]) > .01 and max(m4[k]['raw_rgb'][1], f4[k]['raw_rgb'][1]) < .9 for k in keys])
res['raw_green_EV_mount_minus_50mm'] = float(np.median(np.log2(rg[ok])))
for slot, path in (('01', 'research/gr4_dense_returns_r1/local/mount/targets.json'), ('02', 'research/gr4_nega_returns_r1/local/mount/targets.json')):
    t = {(r['page'], r['patch_id']): r for r in json.loads((ROOT / path).read_text())['samples'] if r['supported']}
    kk = [k for k in t if k in m4]
    T = np.array([t[k]['target_lab'] for k in kk]); L4 = lab([m4[k]['jpeg_rgb'] for k in kk])
    k50 = [k for k in kk if k in f4]; T5 = np.array([t[k]['target_lab'] for k in k50]); L5 = lab([f4[k]['jpeg_rgb'] for k in k50])
    g = np.hypot(*L4[:, 1:].T) < 8
    res[f'target{slot}'] = dict(n=len(kk), target_minus_mount04_dL=float(np.median(T[:, 0] - L4[:, 0])),
        target_minus_mount04_dL_grey=float(np.median(T[g, 0] - L4[g, 0])),
        target_minus_50mm04_dL=float(np.median(T5[:, 0] - L5[:, 0])),
        dE00_mount04_to_target=float(np.median(M.fs.delta_e00(L4, T))), dE00_50mm04_to_target=float(np.median(M.fs.delta_e00(L5, T5))))
dump(LOCAL / 'q2_anchor.json', res)
print(json.dumps(res, indent=1, default=float))
