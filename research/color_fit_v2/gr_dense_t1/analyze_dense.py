"""Baseline scores, hue by lightness strata and exact DE00 residual accounting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import csv
import inspect
import numpy as np


def decomposition(target, pred):
    # Recover the standard normalized L/C/H terms before Cholesky rotation.
    code = inspect.getsource(r.FS.de00_components)
    code = code.replace('def de00_components(', 'def natural_components(')
    code = code[:code.rindex('    return ')] + '    return np.stack([x, y, z], axis=-1), Rt\n'
    ns = {'np': np}
    exec(code, ns)
    v, rt = ns['natural_components'](target, pred)
    interaction = rt*v[:, 1]*v[:, 2]
    energy = v*v
    energy[:, 1:] += interaction[:, None]/2
    total = r.FS.delta_e00(target, pred)**2
    assert np.max(abs(energy.sum(axis=1)-total), initial=0) < 1e-8
    rawC = np.hypot(pred[:, 1], pred[:, 2])-np.hypot(target[:, 1], target[:, 2])
    dh = np.degrees(np.angle((pred[:, 1]+1j*pred[:, 2])/(target[:, 1]+1j*target[:, 2]+1e-20)))
    denom = float(total.sum())
    counter = pred.copy()
    counter[:, 0] = target[:, 0]
    return dict(n=len(target), signed_delta_L_median=float(np.median(pred[:, 0]-target[:, 0])) if len(target) else None,
                abs_delta_L=r.stats(abs(pred[:, 0]-target[:, 0])), abs_delta_C=r.stats(abs(rawC)),
                abs_delta_hue_deg=r.stats(abs(dh)),
                exact_squared_DE00_energy_fraction=dict(zip(('L', 'C_half_interaction', 'H_half_interaction'),
                    (energy.sum(axis=0)/denom).tolist())) if denom else None,
                residual_after_per_point_perfect_L=r.stats(r.FS.delta_e00(target, counter)))


def main():
    rows, strata, residual_rows = {}, [], []
    for group in ('gr3', 'gr4_hdf'):
        for slot in ('01', '02'):
            key = group+'_'+slot
            d = r.P.dense(group, slot)
            target, valid = r.P.observed_targets(group, slot, d, r.transfer(group, slot))
            base = r.FS.lab_from_codes(d['rgb04'])
            L, C, h = r.FS.lch(base)
            rec = dict(group=group, slot=slot, observed_coverage_points=int(valid.sum()), models={})
            for iso in (200, 1600):
                D = r.data(slot, iso)
                pred = r.P.prediction(D, D.current, d['input_x'])
                smoothvalid = d['mode_supported'] & d['standard_supported']
                rec['models'][str(iso)] = dict(
                    observed_dense=r.score(target[valid], pred[valid], base[valid]),
                    smooth_dense=r.score(d['aux_target'][smoothvalid], pred[smoothvalid], base[smoothvalid]),
                    residual=decomposition(target[valid], pred[valid]))
                if iso != 200:
                    continue
                for lo in range(0, 360, 30):
                    mask = valid & (C >= 8) & (h >= lo) & (h < lo+30)
                    dec = decomposition(target[mask], pred[mask])
                    residual_rows.append(dict(group=group, slot=slot, hue_start=lo,
                        n=int(mask.sum()), median_delta_L=dec['signed_delta_L_median'],
                        median_abs_delta_L=dec['abs_delta_L']['median'],
                        median_abs_delta_C=dec['abs_delta_C']['median'],
                        median_abs_delta_hue_deg=dec['abs_delta_hue_deg']['median'],
                        L_energy_fraction=(dec['exact_squared_DE00_energy_fraction'] or {}).get('L')))
                    for lightbin in range(5):
                        lm = (L >= lightbin*20) & (L < (lightbin+1)*20) if lightbin < 4 else L >= 80
                        use = mask & lm
                        sc = r.score(target[use], pred[use], base[use])
                        strata.append(dict(group=group, slot=slot, hue_start=lo, L_start=20*lightbin,
                                           **{k: sc[k] for k in ('n', 'median', 'p90', 'similarity')},
                                           **sc['fractions']))
                mask = valid & (C < 8)
                rec['neutral_dense'] = r.score(target[mask], pred[mask], base[mask])
            # Recompute the older chart, LOO and two distinct rings from integers.
            old = {}
            for iso in (200, 1600):
                D = r.data(slot, iso)
                x = D.a['chart_x'][D.chrom]*D.a['exposure']
                chartbase = r.FS.lab_from_codes(D.a['chart_rgb04'][D.chrom])
                ev = D.evaluate(D.current)
                loo, den = [], []
                for i in D.chrom:
                    fold = r.P.baseline_fold(slot, int(i))
                    error = r.FS.delta_e00(D.a['chart_target'][i], r.P.prediction(D, fold,
                        D.a['chart_x'][[i]]*D.a['exposure'])[0])
                    assert abs(error-fold['held_out'][str(iso)]) < 1e-9
                    loo.append(error)
                    den.append(r.FS.delta_e00(D.a['chart_target'][i], r.FS.lab_from_codes(D.a['chart_rgb04'][i])))
                old[str(iso)] = dict(chart_training=r.score(D.a['chart_target'][D.chrom],
                    r.P.prediction(D, D.current, x), chartbase),
                    loo={**r.stats(loo), 'stock04_median':float(np.median(den)),
                         'similarity':1-float(np.median(loo))/float(np.median(den)),
                         'fractions':{f'lt{k}':float((np.array(loo)<k).mean()) for k in (1,2,3)}},
                    old_hue_interpolated_ring=ev['hue_interpolated_ring']['statistics'],
                    synthetic_firmware_ring=ev['synthetic_target_ring']['statistics'])
            rec['old_protocols'] = old
            rows[key] = rec
            s = rec['models']['200']['observed_dense']
            print(key, 'similarity', round(s['similarity'],6), 'median', round(s['median'],6),
                  'p90',round(s['p90'],6),'Lshare',round(rec['models']['200']['residual']['exact_squared_DE00_energy_fraction']['L'],6), flush=True)
    r.dump(r.HERE/'baseline_metrics.json', rows)
    for name, records in [('strata_round5.csv', strata), ('residual_by_hue.csv', residual_rows)]:
        with (r.HERE/name).open('w', newline='') as f:
            writer=csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(records)


if __name__ == '__main__':
    main()
