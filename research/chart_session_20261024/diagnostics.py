"""Detailed exclusions, repeat stability, and independent adapter checks. No refit."""
import collections
import csv
import json
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import session_runtime as s


def main():
    out = s.LOCAL / 'analysis-final'
    a, chain, p = s.setup(s.LOCAL / 'extraction', freeze=False)
    import analyzer_scoring as scoring
    e = chain.model.Engine(s.TABLE, provenance=p)
    frames = {f['frame']: f for f in [json.loads(x.read_text()) for x in (out / 'frames').glob('*.json')]}
    scores = json.loads((out / 'scores_C/scores.json').read_text())
    targets = chain.targets.Targets(e, p)
    exclusions, counts, measurement = [], {}, {}
    identity = json.loads((out / 'identities.json').read_text())
    for slot, group in identity['C_segments'].items():
        counter = collections.Counter()
        valid_keys = set()
        for key in group['frames']:
            f = frames[key]
            counter.update(flag for q in f['patches'] for flag in q['flags'])
            valid_keys.update(q['patch_id'] for q in f['patches'] if q['valid'])
        measurement[slot] = {'valid': len(valid_keys), 'total': 696, 'flags': dict(counter)}
    for key, result in scores['frames'].items():
        f, base = frames[key], frames[result['matched04']]
        bx, bad = e.invert04(np.array([q['jpeg_rgb'] for q in base['patches']]),
                            np.array([q['raw_wb'] for q in base['patches']]))
        own_unsupported = set(result['target_definition'].get('unsupported_patches', []))
        base_unsupported = set()
        if f['slot'] == '03':
            bf = scoring.as_measure_frame(base)
            _, definition = targets.render({**bf, 'slot': '03'}, bf, bx, e.predict('04', bx))
            base_unsupported = set(definition.get('unsupported_patches', []))
        counter = counts.setdefault(f['slot'], collections.Counter())
        for i, (q, bq) in enumerate(zip(f['patches'], base['patches'])):
            reasons = list(q['flags'])
            reasons += ['paired04:' + r for r in bq['flags']]
            if bad[i]:
                reasons.append('paired04-inverse-out-of-support')
            if min(bq['raw_wb']) <= 1e-6:
                reasons.append('paired04-RAW-too-small')
            if i in own_unsupported:
                reasons.append('recipe-target-out-of-support')
            if i in base_unsupported:
                reasons.append('paired04-target-out-of-support')
            assert bool(result['valid'][i]) == (not reasons), (key, i, reasons)
            counter.update(reasons)
            if reasons:
                exclusions.append({'frame': key, 'slot': f['slot'], 'page': f['page'], 'patch_id': q['patch_id'],
                    'sample_key': q['sample_key'], 'reasons': reasons, 'own_measurement_valid': q['valid'],
                    'paired04_measurement_valid': bq['valid']})
    with (out / 'excluded_patches_detailed.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(exclusions[0]))
        writer.writeheader()
        for row in exclusions:
            writer.writerow({**row, 'reasons': json.dumps(row['reasons'], ensure_ascii=False)})
    white = [f for f in sorted(frames.values(), key=lambda f: f['frame']) if f['capture_group'] == 'C' and f['kind'] == 'white']
    usable = [f for f in white if f['patches'][0]['raw']['clip_frac'] <= .001]
    raw_y = np.array([f['patches'][0]['raw_rgb'] for f in usable]) @ [.25, .5, .25]
    ev = np.log2(raw_y / raw_y[0])
    white_drift = {'frames': [f['frame'] for f in usable], 'relative_raw_EV': ev.tolist(),
        'first_to_last_EV': float(ev[-1]), 'range_EV': float(np.ptp(ev)),
        'status': 'within-0.03EV' if abs(ev[-1]) <= .03 else 'raw-drift-detected',
        'raw_quality': 'RAW saturation checked; JPEG clipping/recipe differences do not exclude RAW-only comparison',
        'does_not_establish_JPEG_recipe_drift': True}
    # The main common mask is useful as a selection-bias diagnostic, never a replacement score.
    byslot = {}
    for slot in ('01', '02', '03', '05', '06'):
        lookup = {}
        for key, q in scores['frames'].items():
            f = frames[key]
            if f['slot'] != slot:
                continue
            for i, patch in enumerate(f['patches']):
                if q['valid'][i]:
                    lookup[patch['patch_id']] = (q['de00'][i], q['baseline_de00'][i])
        byslot[slot] = lookup
    common = set.intersection(*(set(v) for v in byslot.values()))
    common_scores = {slot: chain.measure.similarity([lookup[k][0] for k in common], [lookup[k][1] for k in common]) for slot, lookup in byslot.items()}
    # Recompute the T1 result by a separate np.interp implementation with packed A-node decoding.
    rng = np.random.default_rng(24)
    x = rng.uniform(-20, 4120, (512, 3))
    rows = e.entries['06']['written']
    xs = np.array([0, *struct.unpack('>31H', rows[0]), 4095])
    ys = (rows[6][:33], rows[1], rows[6][33:])
    pre = np.column_stack([np.interp(np.clip(x[:, i], 0, 4095), xs, list(ys[i])) for i in range(3)])
    row, A, B = e.parameters('06')
    y, ci = row.apply(pre)
    rgb = e.mm.rgb_from_ycc(y, e.table.forward(ci, e.fs.Z_of_words(A, B, e.ctx))[0])
    max_error = float(np.max(np.abs(rgb - e.predict('06', x, unclipped=True))))
    assert max_error < 1e-8
    shared = list(rows)
    shared[6] = rows[1] + rows[1]
    old = e.entries['06']
    e.entries['06'] = {**old, 'written': tuple(shared)}
    adapted = e.predict('06', x)
    e.entries['06'] = {**old, 'mask': old['mask'] & ~6}
    original = e.predict('06', x)
    e.entries['06'] = old
    shared_error = float(np.max(np.abs(adapted - original)))
    assert shared_error < 1e-8
    s.dump(out / 'diagnostics.json', {'measurement_quality': measurement,
        'scoring_exclusion_reasons': {k: dict(v) for k, v in counts.items()},
        'white_raw_drift': white_drift, 'common_mask': {'n': len(common), 'scores': common_scores,
            'note': 'all-five-slot intersection only; small and selected, not independent generalization'},
        'T1_checks': {'np_interp_max_rgb_error': max_error, 'shared_curve_original_Engine_max_rgb_error': shared_error, 'samples': len(x)}})
    stability = json.loads((out / 'stability.json').read_text())
    stability['C_white_RAW_only'] = white_drift
    s.dump(out / 'stability.json', stability)
    s.dump(out / 'diagnostics_provenance.json', p.finish())
    print(json.dumps({'white_drift': white_drift, 'common_n': len(common), 'T1_max_error': max_error}, ensure_ascii=False))


if __name__ == '__main__':
    main()
