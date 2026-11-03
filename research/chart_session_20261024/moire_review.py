"""Threshold sensitivity and three evidence streams. No color-model refit."""
import argparse
import collections
import copy
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import session_runtime as s
from repair_mount_metadata import apply as mount_adapter

SLOTS = ('01', '02', '03', '05', '06')
MOIRE = ('jpeg1.5', 'jpeg3', 'jpeg6', 'raw0.5pct', 'raw1pct', 'raw2pct', 'none-diagnostic')
CLIP = ('strict', 'recipe-single-channel', 'mild-single-channel', 'recipe-any-diagnostic', 'ignore-diagnostic')


def stats(a):
    a = np.asarray(a, float)
    return {'n': len(a), 'median': float(np.median(a)) if len(a) else None,
            'mean': float(np.mean(a)) if len(a) else None,
            'p90': float(np.percentile(a, 90)) if len(a) else None,
            'p95': float(np.percentile(a, 95)) if len(a) else None,
            'max': float(a.max()) if len(a) else None}


def flagged(row, policy):
    if policy.startswith('jpeg'):
        threshold = float(policy[4:])
        return row['jpeg_spatial']['peak_ratio'] > 25 and row['jpeg_spatial']['amplitude'] > threshold
    if policy.startswith('raw'):
        threshold = float(policy[3:-3]) / 100
        return any(v['peak_ratio'] > 25 and v['amplitude'] > 4 and v['relative_amplitude'] > threshold for v in row['raw_planes'])
    return False


def clip_ok(row, policy, baseline=False):
    c = row['clipping']
    if c['any_fraction'] <= .01:
        return True
    if policy == 'ignore-diagnostic':
        return True
    if policy == 'recipe-any-diagnostic' and not baseline:
        return True
    if policy == 'recipe-single-channel' and not baseline and c['category'] == 'single-channel-color':
        return True
    if policy == 'mild-single-channel':
        mean = np.array(row['jpeg']['mean'])
        return c['category'] == 'single-channel-color' and c['any_fraction'] <= .05 and np.all((mean >= 5) & (mean <= 250))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', default='moire-review-v2')
    args = ap.parse_args()
    out = (s.LOCAL / args.run).resolve()
    assert out.is_relative_to(s.LOCAL) and (out / 'sampling_summary.json').exists()
    assert not (out / 'sensitivity.json').exists()
    a, chain, p = s.setup(s.LOCAL / 'extraction', freeze=False)
    mount_adapter(a, chain)
    import analyzer_scoring as scoring
    p.add(Path(__file__))
    metrics = [json.loads(line) for line in p.add(out / 'roi_metrics.jsonl').read_text().splitlines()]
    rows = {(v['frame'], v['patch_id']): v for v in metrics}
    frames = {f['frame']: f for f in [json.loads(p.add(path).read_text()) for path in sorted((s.LOCAL / 'analysis-final/frames').glob('*.json'))]}
    cframes = [f for f in frames.values() if f['capture_group'] == 'C' and f['kind'] == 'screen']
    baselines = {f['page']: f for f in cframes if f['slot'] == '04'}
    e = chain.model.Engine(s.TABLE, provenance=p)
    reference = baselines[1]
    ds = chain.dng.DngScene(Path(reference['paths']['dng']), Path(reference['paths']['jpeg']), verify=False)
    xyz_basis = ds.xyz(np.eye(3), ds.white_as_shot)[0].T
    for f in cframes:
        assert np.allclose(f['meta']['asn'], reference['meta']['asn'], rtol=0, atol=1e-9)
        raw = np.array([q['raw_rgb'] for q in f['patches']])
        assert np.max(np.abs(raw @ xyz_basis - np.array([q['xyz_camera'] for q in f['patches']]))) < 1e-9
    all_scored, residual_rows = {}, []
    for estimator in ('median', 'trimmed_mean', 'mean'):
        engine = chain.model.Engine(s.TABLE, provenance=p)
        targets = chain.targets.Targets(engine, p)
        adapted = {}
        for f in cframes:
            ff = scoring.as_measure_frame(copy.deepcopy(f))
            rr = [rows[(f['frame'], q['patch_id'])] for q in f['patches']]
            ff['rgb'] = np.array([r['jpeg'][estimator] for r in rr])
            ff['raw_cam'] = np.array([r['raw'][estimator] for r in rr])
            ff['raw_wb'] = ff['raw_cam'] / np.array(f['meta']['asn'])
            ff['xyz_camera'] = ff['raw_cam'] @ xyz_basis
            for i, patch in enumerate(ff['patches']):
                patch['rgb'] = ff['rgb'][i]
                patch['flags'] = [flag for flag in patch['flags'] if flag not in ('moire-suspect', 'jpeg-clipping')]
            adapted[f['frame']] = ff
        scored = {}
        for f in cframes:
            ff, bb = adapted[f['frame']], adapted[baselines[f['page']]['frame']]
            # A fresh patch list prevents flags added by one scoring call from contaminating another call.
            result = chain.measure.score_record(engine, targets, copy.deepcopy(ff), copy.deepcopy(bb))
            result['matched04'] = bb['id']
            scored[f['frame']] = result
            if estimator == 'mean':
                direct_rgb = engine.predict(f['slot'], ff['raw_wb'] * 4095)
                direct_lab = engine.fs.lab_from_codes(direct_rgb)
                lab = engine.fs.lab_from_codes(ff['rgb'])
                direct_de = engine.fs.delta_e00(lab, direct_lab)
                for i, patch in enumerate(f['patches']):
                    r = rows[(f['frame'], patch['patch_id'])]
                    tm = np.array(r['jpeg']['trimmed_mean'])
                    med = np.array(r['jpeg']['median'])
                    shifted = engine.fs.lab_from_codes(r['jpeg_shifted_means'])
                    center_lab = engine.fs.lab_from_codes(np.array([r['jpeg']['mean']]))
                    shifts = engine.fs.delta_e00(shifted, np.broadcast_to(center_lab, shifted.shape))
                    residual_rows.append({'frame': f['frame'], 'page': f['page'], 'patch_id': patch['patch_id'],
                        'slot': f['slot'], 'flagged_jpeg1.5': flagged(r, 'jpeg1.5'),
                        'jpeg_amplitude': r['jpeg_spatial']['amplitude'], 'raw_flag_1pct': flagged(r, 'raw1pct'),
                        'clip_category': r['clipping']['category'], 'clip_fraction': r['clipping']['any_fraction'],
                        'raw_saturation_fraction': r['raw_saturation_fraction'],
                        'nominal_L': r['nominal_lab_d65'][0], 'nominal_C': float(np.hypot(*r['nominal_lab_d65'][1:])),
                        'direct_model_de00': float(direct_de[i]), 'direct_model_lab_residual': (lab[i]-direct_lab[i]).tolist(),
                        'conditioned04_model_de00': float(result['model_de00'][i]),
                        'trimmed_mean_minus_median_rgb': (tm-med).tolist(),
                        'trimmed_mean_median_de00': float(engine.fs.delta_e00(engine.fs.lab_from_codes(tm[None]), engine.fs.lab_from_codes(med[None]))[0]),
                        'mean_median_de00': float(engine.fs.delta_e00(center_lab, engine.fs.lab_from_codes(med[None]))[0]),
                        'shift2px_max_de00': float(max(shifts)),
                        'autocorrelation_lag1': r['jpeg_spatial']['autocorrelation_lags']['1'],
                        'detrended_quadrant_mean_range': r['jpeg_spatial']['detrended_quadrant_mean_range']})
        all_scored[estimator] = scored
        numeric = {}
        for key, q in scored.items():
            numeric[key] = {k: q[k] for k in ('matched04','slot','valid','de00','baseline_de00','model_de00','target_lab',
                            'baseline_target_lab','hue_deg','input_lightness_Lstar','model_rgb','observed_lab')}
        s.dump(out / 'scored' / (estimator + '.json'), numeric)
        print(f'Unfiltered model/target rendering complete: {estimator}', flush=True)
    results = []
    for estimator, scored in all_scored.items():
        for moire in MOIRE:
            for clipping in CLIP:
                for slot in ('04', *SLOTS):
                    data, base, model, hue = [], [], [], []
                    selected_keys = []
                    for key, q in scored.items():
                        f = frames[key]
                        if f['slot'] != slot:
                            continue
                        base_frame = baselines[f['page']]
                        mask = np.array(q['valid'], bool)
                        for i, patch in enumerate(f['patches']):
                            r, b = rows[(key, patch['patch_id'])], rows[(base_frame['frame'], patch['patch_id'])]
                            mask[i] &= not flagged(r, moire) and not flagged(b, moire)
                            mask[i] &= clip_ok(r, clipping) and clip_ok(b, clipping, baseline=True)
                            if mask[i]:
                                selected_keys.append([key, patch['patch_id']])
                        data.extend(np.array(q['de00'])[mask]); base.extend(np.array(q['baseline_de00'])[mask]); model.extend(np.array(q['model_de00'])[mask])
                        chromatic = np.array([not p['gray'] for p in q['patches']])
                        hue.extend(np.floor(np.array(q['hue_deg'])[mask & chromatic]/15).astype(int).tolist())
                    sim = chain.measure.similarity(data, base)
                    results.append({'estimator': estimator, 'moire_policy': moire, 'clipping_policy': clipping,
                        'slot': slot, 'n': len(data), 'hue_sectors': len(set(hue)), 'similarity': sim['value'],
                        'de00': stats(data), 'baseline_de00': stats(base), 'model_de00': stats(model),
                        'selected_keys': selected_keys})
    # Exact reconstruction of the frozen 1.5-code median result is a real regression check.
    old = json.loads((s.LOCAL/'analysis-final/scores_C/scores.json').read_text())['slots']
    for slot in SLOTS:
        q = next(x for x in results if x['estimator']=='median' and x['moire_policy']=='jpeg1.5' and x['clipping_policy']=='strict' and x['slot']==slot)
        assert q['n'] == old[slot]['measured_vs_target']['n']
        assert abs(q['similarity'] - old[slot]['similarity']['value']) < 1e-9
    s.dump(out / 'sensitivity.json', {'schema': 'moire-threshold-sensitivity/1', 'cases': results,
        'RAW_rule': 'separate CFA phases; high-frequency >=0.2 cycles/CFA-sample; spectral peak ratio>25; amplitude>4 normalized 12-bit DN and >relative threshold',
        'original_1p5_median_results_reproduced': True})
    fields = ('estimator','moire_policy','clipping_policy','slot','n','hue_sectors','similarity','median_de00','p90_de00','model_median_de00')
    with (out / 'sensitivity.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields);w.writeheader()
        for q in results:
            w.writerow({**{k:q[k] for k in fields[:7]}, 'median_de00':q['de00']['median'],
                        'p90_de00':q['de00']['p90'], 'model_median_de00':q['model_de00']['median']})
    s.dump(out / 'model_residuals_and_ROI.json', residual_rows)
    evidence = {}
    for slot in ('all', '04', *SLOTS):
        selected = [r for r in residual_rows if (slot=='all' or r['slot']==slot) and r['clip_fraction']<=.01 and r['raw_saturation_fraction']<=.001]
        evidence[slot] = {}
        for flag in (False, True):
            group = [r for r in selected if r['flagged_jpeg1.5']==flag]
            evidence[slot]['flagged' if flag else 'unflagged'] = {field: stats([r[field] for r in group]) for field in
                ('direct_model_de00','conditioned04_model_de00','trimmed_mean_median_de00','mean_median_de00','shift2px_max_de00')}
        buckets = collections.defaultdict(lambda: [[], []])
        for r in selected:
            bucket = (r['slot'], int(r['nominal_L']//10), int(r['nominal_C']//20))
            buckets[bucket][int(r['flagged_jpeg1.5'])].append(r['direct_model_de00'])
        pairs = [(min(len(a), len(b)), float(np.median(b)-np.median(a))) for a,b in buckets.values() if a and b]
        evidence[slot]['L_C_recipe_matched'] = {'strata':len(pairs), 'matched_weight':sum(n for n,d in pairs),
            'weighted_median_gap_mean':sum(n*d for n,d in pairs)/sum(n for n,d in pairs) if pairs else None,
            'note':'difference in per-stratum median direct-model DE00; color/model confounding is not eliminated'}
    # Mount P1 repeat: different shutter, so use native RAW / exposure time, not raw JPEG differences as a drift claim.
    first = {r['patch_id']:r for r in metrics if r['frame']=='R8051261'}
    second = {r['patch_id']:r for r in metrics if r['frame']=='R8051262'}
    repeats = []
    for key in sorted(first):
        a1, b1 = first[key], second[key]
        if max(a1['raw_saturation_fraction'],b1['raw_saturation_fraction']) > .001:
            continue
        ra, rb = np.array(a1['raw']['mean'])/a1['shutter_s'], np.array(b1['raw']['mean'])/b1['shutter_s']
        ev = np.log2(np.maximum(rb,1e-9)/np.maximum(ra,1e-9))
        rga = np.array([ra[0]/max(ra[1],1e-9),ra[2]/max(ra[1],1e-9)])
        rgb = np.array([rb[0]/max(rb[1],1e-9),rb[2]/max(rb[1],1e-9)])
        repeats.append({'patch_id':key, 'jpeg_flagged_either':flagged(a1,'jpeg1.5') or flagged(b1,'jpeg1.5'),
            'raw_flagged_either':flagged(a1,'raw1pct') or flagged(b1,'raw1pct'),
            'raw_exposure_normalized_EV_RGB':ev.tolist(),
            'raw_chromaticity_relative_difference':(rgb/np.maximum(rga,1e-9)-1).tolist(),
            'unadjusted_JPEG_de00':float(e.fs.delta_e00(e.fs.lab_from_codes(np.array([a1['jpeg']['mean']])),e.fs.lab_from_codes(np.array([b1['jpeg']['mean']])))[0])})
    global_ev = np.median(np.array([r['raw_exposure_normalized_EV_RGB'] for r in repeats]),axis=0)
    for r in repeats:
        r['global_EV_removed_abs_RGB'] = np.abs(np.array(r['raw_exposure_normalized_EV_RGB'])-global_ev).tolist()
    repeat_summary = {'n':len(repeats), 'jpeg_flagged_either':sum(r['jpeg_flagged_either'] for r in repeats),
        'raw_flagged_either':sum(r['raw_flagged_either'] for r in repeats), 'global_normalized_EV_RGB':global_ev.tolist(),
        'relative_chromaticity_error':stats([abs(x) for r in repeats for x in r['raw_chromaticity_relative_difference']]),
        'global_EV_removed_abs_RGB':stats([x for r in repeats for x in r['global_EV_removed_abs_RGB']]),
        'unadjusted_JPEG_de00':stats([r['unadjusted_JPEG_de00'] for r in repeats]),
        'scope':'MOUNT native04 at 1/80 vs1/100; not a repeated 50mm high-moire trial', 'patches':repeats}
    clip_summary = {}
    for group in ('C','M'):
        rr = [r for r in metrics if r['group']==group]
        clip_summary[group] = {c: {'n':sum(r['clipping']['category']==c for r in rr),
            'raw_unsaturated':sum(r['clipping']['category']==c and r['raw_saturation_fraction']<=.001 for r in rr),
            'unclipped_channel_observations':sum(sum(r['clipping']['unclipped_channel_mask']) for r in rr if r['clipping']['category']==c)}
            for c in sorted({r['clipping']['category'] for r in rr})}
    cohorts = {}
    for name, lo, hi in (('original<=1.5',0,1.5),('new1.5to3',1.5,3),('new3to6',3,6),('over6',6,float('inf'))):
        group = [r for r in residual_rows if r['slot']=='04' and r['clip_fraction']<=.01 and
                 r['raw_saturation_fraction']<=.001 and lo < r['jpeg_amplitude'] <= hi]
        cohorts[name] = {key:stats([r[key] for r in group]) for key in
            ('direct_model_de00','trimmed_mean_median_de00','mean_median_de00','shift2px_max_de00')}
        cohorts[name]['abs_autocorrelation_lag1'] = stats([abs(r['autocorrelation_lag1']) for r in group])
        cohorts[name]['quadrant_range_max_code'] = stats([max(r['detrended_quadrant_mean_range']) for r in group])
    s.dump(out / 'evidence.json', {'model_and_ROI':evidence, 'Mount_repeat':repeat_summary, 'clipping':clip_summary,
        '04_threshold_cohorts':cohorts,
        'C_white_RAW_stability':json.loads((s.LOCAL/'analysis-final/diagnostics.json').read_text())['white_raw_drift'],
        '04_conditioned_model_is_circular':True, 'XYZ_basis_verified_for_all_C_patches':True})
    s.dump(out / 'review_provenance.json', p.finish())
    print(json.dumps({'cases':len(results), 'Mount_repeat_n':len(repeats), 'old_result_reproduced':True}), flush=True)


if __name__ == '__main__':
    main()
