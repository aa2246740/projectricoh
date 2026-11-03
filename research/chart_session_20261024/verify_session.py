"""Read actual output artifacts and independently recompute reported aggregates. No fits."""
import argparse
import collections
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image
import session_runtime as s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', default='analysis-final')
    args = ap.parse_args()
    s.guard()
    out = s.LOCAL / args.analysis
    frames = json.loads((out / 'frame_assignments.json').read_text())
    assert len(frames) == 51 and all(int(f['frame'][1:]) % 10000 >= 1261 for f in frames)
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['exclude'] == [f'R805{n}' for n in range(1229, 1261)]
    assert all(manifest['frames'][key]['purpose'] == 'trial' for key in manifest['exclude'])
    assert sum(f['kind'] == 'white' for f in frames) == 8
    ids = json.loads((out / 'identities.json').read_text())
    assert all(g['sequence_confirmed'] for g in ids['C_segments'].values())
    assert all(sorted(g['pages']) == list(range(1, 7)) for g in ids['C_segments'].values())
    assert not any(int(key[1:]) % 10000 < 1269 for key in ids['frames'])
    direct04 = {}
    for frame in ids['C_segments']['04']['frames']:
        candidates = ids['frames'][frame]['raw_direct_candidate_de00']
        best = min(candidates, key=lambda key: candidates[key]['median'])
        assert best == '04', (frame, best)
        direct04[frame] = candidates[best]['median']
    scores = json.loads((out / 'scores_C/scores.json').read_text())
    assert not scores['errors']
    metrics = {}
    byid = {f['frame']: f for f in frames}
    for slot in ('01', '02', '03', '04', '05', '06'):
        rows = [q for key, q in scores['frames'].items() if byid[key]['slot'] == slot]
        valid = np.concatenate([np.array(q['valid'], bool) for q in rows])
        de = np.concatenate([np.array(q['de00']) for q in rows])[valid]
        base = np.concatenate([np.array(q['baseline_de00']) for q in rows])[valid]
        summary = scores['slots'][slot]
        assert len(de) == summary['measured_vs_target']['n']
        assert abs(float(np.median(de)) - summary['measured_vs_target']['median']) < 1e-12
        sim = 1 - float(np.median(de)) / float(np.median(base)) if np.median(base) >= .25 else None
        assert sim is None and summary['similarity']['value'] is None or abs(sim - summary['similarity']['value']) < 1e-12
        metrics[slot] = {'n': len(de), 'median_de00': float(np.median(de)), 'similarity': sim,
                         'hue_sectors_with_samples': sum(h['n'] > 0 for h in summary['per_hue'])}
    # Read the actual interchange parser, without invoking any solver.
    sys.path.insert(0, str(s.ROOT / 'research/module_adapt'))
    import calibrate
    exchange_checks = {}
    a, chain, _ = s.setup(s.LOCAL / 'extraction', freeze=False)
    for unit in ('50mm', 'mount'):
        folder = out / 'exchange' / unit
        meta = json.loads((folder / 'frames.json').read_text())
        rows = [json.loads(line) for line in (folder / 'patches.jsonl').read_text().splitlines()]
        assert len({(r['frame'], r['page'], r['patch_id']) for r in rows}) == len(rows)
        assert all(int(r['frame'][1:]) % 10000 >= 1261 for r in rows)
        for r in rows:
            assert isinstance(r['valid'], bool)
            if r['valid']:
                assert len(r['raw_rgb']) == len(r['jpeg_rgb']) == 3
                assert np.isfinite(r['raw_rgb']).all() and np.isfinite(r['jpeg_rgb']).all()
                assert np.all((np.array(r['raw_rgb']) >= 0) & (np.array(r['raw_rgb']) <= 1))
                assert np.all((np.array(r['jpeg_rgb']) >= 0) & (np.array(r['jpeg_rgb']) <= 255))
        details = {'frames': len(meta['frames']), 'patches': len(rows), 'measurement_valid': sum(r['valid'] for r in rows)}
        if unit == '50mm':
            usable = {}
            for slot in ('01', '02', '03', '04', '05', '06'):
                selected, _ = calibrate.load_exchange(folder / 'patches.jsonl', folder / 'frames.json', unit, slot)
                usable[slot] = {'usable': sum(r['usable'] for r in selected),
                    'by_page': dict(collections.Counter(str(r['page']) for r in selected if r['usable']))}
            details['calibrate_parser'] = 'passed without fitting'
            details['usable_by_slot'] = usable
            display = json.loads((s.ROOT / 'research/stage2e_verification/local/measurements.json').read_text())['frames']['R8051160']['meta']['display']
            names = ('contrast', 'sharpness', 'vividness', 'orange_saturation', 'green_saturation',
                     'blue_saturation', 'red_saturation', 'magenta_saturation',
                     'orange_hue', 'green_hue', 'blue_hue', 'red_hue', 'magenta_hue')
            inverse_mapping = {v: k for k, v in chain.dng.analyze_capture().RAW_TO_DISPLAY.items()}
            expected = [inverse_mapping[display[k]] for k in names]
            assert all(f['selector_bytes']['raw13'] == expected and f['selector_bytes']['type26_control'] == 2
                       for f in meta['frames'].values() if f['selector_bytes']['recipe_slot'] == '04')
            details['stock_selector_and_slider_contract'] = 'passed'
        else:
            assert not meta['metadata_complete']
            assert all(f['aperture_f'] is None and f['lens_id'] is None for f in meta['frames'].values())
            details['calibrate_parser'] = 'blocked deliberately: unknown actual aperture/lens/corrections'
        # Recompute a JPEG mean from source pixels independently of the saved numbers.
        chosen = next(r for r in rows if r['valid'])
        f = json.loads((out / 'frames' / (chosen['frame'] + '.json')).read_text())
        patch = next(p for p in f['patches'] if p['patch_id'] == chosen['patch_id'])
        H = np.asarray(f['geometry']['H'])
        with Image.open(f['paths']['jpeg']) as im:
            rgb = np.asarray(im.convert('RGB'))
        ya, yb, xa, xb, mask, _ = chain.ar.roi_mask({'H': H, 'Hinv': np.linalg.inv(H)}, patch['chart_roi_bbox'], rgb.shape)
        expected = rgb[ya:yb, xa:xb][mask].mean(axis=0)
        assert np.max(np.abs(expected - chosen['jpeg_rgb'])) < 1e-12
        assert chosen['raw_rgb'] == patch['raw']['mean_cam']
        details['independent_source_mean_check'] = {'frame': chosen['frame'], 'patch_id': chosen['patch_id'], 'max_error': 0}
        exchange_checks[unit] = details
    source_checks = {}
    for row in frames:
        record = json.loads((out / 'frames' / (row['frame'] + '.json')).read_text())
        for field, key in (('jpeg', 'JPEG'), ('dng', 'DNG')):
            path, digest = record['paths'][field], record['hashes'][key]
            assert s.sha(path) == digest, path
            source_checks[path] = digest
    for file in (out / 'provenance.json', s.LOCAL / 'mount_repaired/provenance.json'):
        for path, row in json.loads(file.read_text()).items():
            assert row['unchanged'] and s.sha(path) == row['sha256'], path
            source_checks[path] = row['sha256']
    sealed = {}
    for name in ('SHA256SUMS', 'ANALYZER_SHA256SUMS'):
        records = (s.CHART / name).read_text().splitlines()
        for line in records:
            digest, rel = line.split(maxsplit=1)
            assert s.sha(s.CHART / rel.lstrip('*')) == digest, rel
        sealed[name] = len(records)
    s.dump(out / 'verification.json', {'passed': True, 'accepted_frames': len(frames),
        'excluded_A': 32, 'metrics_independently_recomputed': metrics,
        'exchange': exchange_checks, 'unchanged_inputs_verified': len(source_checks), 'chart_seals': sealed,
        '04_RAW_direct_prediction_all_six_pages_best_04': direct04,
        'no_fit_executed': True, 'no_camera_or_card_access': True})
    print(json.dumps({'passed': True, 'frames': len(frames), 'inputs_unchanged': len(source_checks), 'metrics': metrics}, ensure_ascii=False))


if __name__ == '__main__':
    main()
