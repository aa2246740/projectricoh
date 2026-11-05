"""Reproducible firmware-only module comparisons and conditional target scores."""
import csv
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s
from unit_model import UnitModel

SLOTS = ('01', '02', '03', '05', '06')
P3_TO_XYZ = np.array([[.4865709486, .2656676932, .1982172852],
                     [.2289745641, .6917385218, .0792869141],
                     [0., .0451133819, 1.0439443689]])


def synthetic_inputs(model):
    fs, mm = model.fs, model.mm
    fuji = s.read('research/fuji_phase2/local/fit.json')
    labs = fs.chart_xyz_d65(fuji)
    card_linear = np.array([labs[k] @ np.linalg.inv(fs.M709).T for k in fs.LABELS])
    p = s.source(s.ROOT / 'research/color_fit_v2/05_classic_chrome/round4/local/cache/data_200.npz')
    with np.load(p, allow_pickle=False) as z:
        # A shared 50mm chart approximation establishes a synthetic scene coordinate.
        # It is never described as the spectral response of the other two modules.
        chart_x = z['chart_x'].copy()
    transform = np.linalg.lstsq(card_linear, chart_x, rcond=None)[0]
    fit_error = np.linalg.norm(card_linear@transform-chart_x, axis=1)
    card = card_linear @ transform

    h, y, r = np.meshgrid(np.arange(0., 360., .5), (64., 128., 192.), (10., 30., 50.), indexing='ij')
    ci = r.ravel()*np.exp(1j*np.deg2rad(h.ravel()))
    pre = model.stock_matrix.invert(y.ravel(), ci)
    ok = np.all((pre > 1) & (pre < 254), axis=1)
    ring = model.curve04.inverse(pre[ok])

    grid = np.array(np.meshgrid(*([np.linspace(0, 1, 13)]*3), indexing='ij')).reshape(3, -1).T
    lin_p3 = fs.srgb_to_linear(grid)
    srgb_linear = lin_p3 @ P3_TO_XYZ.T @ np.linalg.inv(fs.M709).T
    raw_p3 = srgb_linear @ transform
    valid = np.all((raw_p3 >= 0) & (raw_p3 <= 4095), axis=1)
    samples = {'hue_ring': ring, 'colorchecker24': card, 'p3_grid13': raw_p3[valid]}
    detail = {'scene_to_camera_matrix': transform, 'matrix_fit_residual_12bit': s.stats(fit_error),
              'p3_grid_total': len(grid), 'p3_physical_inputs': int(valid.sum()),
              'p3_rejected_inputs': int((~valid).sum()),
              'p3_outside_srgb_input_count': int(np.any((srgb_linear < 0) | (srgb_linear > 1), axis=1).sum()),
              'p3_outside_srgb_retained': int((valid & np.any((srgb_linear < 0) | (srgb_linear > 1), axis=1)).sum()),
              'p3_encoding': 'Display P3 D65; sRGB transfer; no sRGB gamut clipping before camera projection',
              'module_scene_spectral_equivalence_proven': False}
    return samples, detail


def hue_bins(model, x):
    _, c = model.stock_matrix.apply(model.curve04(x))
    h = model.mm.hue_deg(c)
    # Hue becomes numerically arbitrary near the neutral axis.
    out = np.floor(h/15).astype(int) % 24
    out[abs(c) < 1.] = -1
    return out, h


def compare(models, samples, name):
    result = {'domain': name, 'datasets': {}, 'sectors': [], 'native_sectors': []}
    ref = models['50mm']
    for dataset, x in samples.items():
        bins, hue = hue_bins(ref, x)
        if dataset == 'colorchecker24':
            bins[-6:] = -1
        _, ci = ref.stock_matrix.apply(ref.curve04(x))
        native = np.argmax(ref.table.kernel_weights(hue, abs(ci)), axis=1)
        native[bins < 0] = -1
        pairs = [('50mm', '28mm'), ('50mm', 'mount'), ('28mm', 'mount')]
        for slot in ('04', *SLOTS):
            rgb = {k: m.predict(slot, x) for k, m in models.items()}
            for a, b in pairs:
                delta = ref.de(rgb[a], rgb[b])
                key = f'{slot}/{a}:{b}'
                result['datasets'].setdefault(dataset, {})[key] = s.stats(delta)
                for sector in range(24):
                    sel = bins == sector
                    result['sectors'].append({'domain': name, 'dataset': dataset, 'slot': slot,
                        'pair': a+':'+b, 'sector_15deg': sector, 'hue_start': 15*sector,
                        'hue_end': 15*(sector+1), **s.stats(delta[sel])})
                    selected_native = native == sector
                    result['native_sectors'].append({'domain': name, 'dataset': dataset, 'slot': slot,
                        'pair': a+':'+b, 'colour_record_0based': sector, **s.stats(delta[selected_native])})
            for unit, m in models.items():
                raw = m.predict(slot, x, unclipped=True)
                result['datasets'][dataset].setdefault('clipping', {})[slot+'/'+unit] = float(np.mean(np.any((raw < 0) | (raw > 255), axis=1)))
        result['datasets'][dataset]['neutral_samples'] = int((bins < 0).sum())
    return result


def conditional_target_scores(models):
    # Already-measured 50mm scene coordinates and fixed external target definitions.
    # The new modules have no measured input mapping yet.
    measured = s.read('research/closed_loop/local/m20261021_r1.json')
    result = {}
    for slot in SLOTS:
        f = next(f for f in measured['frames'] if f['id'] == 'screen'+slot)
        x = np.array(f['input_x'])
        bx = np.array(f['baseline_input_x'])
        target = np.array(f['target_lab'])
        baseline_target = np.array(f['baseline_target_lab'])
        valid = np.array(f['valid'], bool)
        for unit, model in models.items():
            error = model.fs.delta_e00(model.fs.lab_from_codes(model.predict(slot, x)), target)
            baseline = model.fs.delta_e00(model.fs.lab_from_codes(model.predict('04', bx)), baseline_target)
            result.setdefault(slot, {})[unit] = {'error': s.stats(error[valid]),
                'baseline_error': s.stats(baseline[valid]), 'similarity': s.similarity(error[valid], baseline[valid]),
                'n_invalid': int((~valid).sum()), 'conditional_on_50mm_scene_coordinates': True,
                'actual_unit_camera_validation': False,
                'target_kind': f['target_definition']}
    return result


def main():
    s.guard()
    base = s.engine()
    models = {unit: UnitModel(unit, base=base) for unit in ('50mm', '28mm', 'mount')}
    ideal = {unit: UnitModel(unit, base=base, ideal=True) for unit in models}
    samples, scene = synthetic_inputs(models['50mm'])
    runs = [compare(models, samples, 'borrowed_50mm_response'), compare(ideal, samples, 'ideal_gain1_k1')]
    scores = conditional_target_scores(models)
    private = {'schema': 'module-adapt-predictions/1', 'scene_projection': scene,
               'models': {k: v.describe() for k, v in models.items()}, 'comparisons': runs,
               'target_scores': scores, 'synthetic_inputs': samples,
               'sector_definition': '15 degree pre-table BT.601 bins in the 50mm input coordinate, not Lab hue',
               'native_sector_definition': 'largest 50mm empirical kernel weight among the 24 native row records; neutral samples excluded; common grouping across modules'}
    s.dump('local/predictions.json', private)
    rows = [row for run in runs for row in run['sectors']]
    with s.output('local/by_hue_sector.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    rows = [row for run in runs for row in run['native_sectors']]
    with s.output('local/by_native_sector.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    s.finish('local/predict_inputs.json')
    summary = {run['domain']: {ds: {key: value for key, value in entries.items() if key.startswith('04/') or key.endswith('50mm:28mm') or key.endswith('50mm:mount')}
               for ds, entries in run['datasets'].items()} for run in runs}
    s.dump('local/prediction_summary.json', {'comparison': summary, 'target_scores': scores})
    for unit in ('28mm', 'mount'):
        q = runs[0]['datasets']['hue_ring']
        print(unit, '04/色相环 median,p90 ΔE00', q['04/50mm:'+unit]['median'], q['04/50mm:'+unit]['p90'])


if __name__ == '__main__':
    main()
