"""Identify recipes, score separate capture groups, and export module exchange data."""
import argparse
import copy
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image
import session_runtime as s

SLOTS = ('01', '02', '03', '04', '05', '06')
C_STARTS = dict(zip(('04', '01', '02', '03', '05', '06'), (1270, 1277, 1284, 1291, 1298, 1305)))


def number(f):
    return int(f['frame'][1:]) % 10000


def read_frames(folder):
    return [json.loads(p.read_text()) for p in sorted((folder / 'frames').glob('*.json'))]


def stat(e):
    e = np.asarray(e)
    return {'n': len(e), 'median': float(np.median(e)) if len(e) else None,
            'p90': float(np.percentile(e, 90)) if len(e) else None,
            'max': float(np.max(e)) if len(e) else None}


def identity(f, base, e, clean=True):
    bx, bad = e.invert04(np.array([p['jpeg_rgb'] for p in base['patches']]),
                        np.array([p['raw_wb'] for p in base['patches']]))
    raw = np.array([p['raw_wb'] for p in f['patches']])
    braw = np.array([p['raw_wb'] for p in base['patches']])
    x = bx * raw / np.maximum(braw, 1e-9)
    obs = e.fs.lab_from_codes([p['jpeg_rgb'] for p in f['patches']])
    valid = ~bad & np.all(braw > 1e-6, axis=1)
    if clean:
        valid &= np.array([p['valid'] and q['valid'] for p, q in zip(f['patches'], base['patches'])])
    errors = {slot: e.fs.delta_e00(obs, e.fs.lab_from_codes(e.predict(slot, x)))[valid] for slot in SLOTS}
    metrics = {k: stat(v) for k, v in errors.items()}
    rank = sorted(SLOTS, key=lambda k: metrics[k]['median'] if metrics[k]['median'] is not None else float('inf'))
    best, second = rank[:2]
    n = len(errors[best])
    gap = (metrics[second]['median'] - metrics[best]['median']) if n else None
    bootstrap = None
    if n:
        rng = np.random.default_rng(20261024)
        ix = rng.integers(0, n, (500, n))
        bootstrap = float(np.mean(np.median(errors[best][ix], axis=1) < np.median(errors[second][ix], axis=1)))
    reliable = bool(n >= 8 and metrics[best]['median'] <= 3 and gap >= .35 and bootstrap >= .99)
    direct = {slot: stat(e.fs.delta_e00(obs, e.fs.lab_from_codes(e.predict(slot, raw * 4095)))[valid]) for slot in SLOTS}
    return {'frame': f['frame'], 'page': f['page'], 'baseline': base['frame'], 'n': n,
            'best_slot': best if n else None, 'runner_up': second if n else None, 'gap_de00': gap,
            'confidence': 'high' if reliable else 'trial', 'reliable': reliable,
            'bootstrap_best_beats_runner_fraction': bootstrap, 'candidate_model_de00': metrics,
            'raw_direct_candidate_de00': direct,
            'confidence_definition': 'n>=8, best median<=3 DE00, runner median gap>=0.35, patch-bootstrap win>=0.99; bootstrap is not a calibrated probability',
            '_errors': errors}


def write_csv(path, rows, fields):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(s.plain(row.get(k)), ensure_ascii=False) if isinstance(row.get(k), (list, dict)) else row.get(k) for k in fields})


def export_exchange(frames, out, analyzer, chain, engine):
    out.mkdir(parents=True, exist_ok=True)
    metadata, rows = {}, []
    for f in frames:
        m = f['meta']
        mount = f['unit'] == 'mount-a12'
        with Image.open(f['paths']['jpeg']) as im:
            rgb = np.asarray(im.convert('RGB'))
            ex = im.getexif().get_ifd(34665)
            color_space = ex.get(40961)
        metadata[f['frame']] = {
            'module': 'mount' if mount else '50mm', 'iso': int(m['iso']), 'shutter_s': m['t'],
            'aperture_f': m['f'], 'aperture_source': 'unknown 0/0 EXIF' if mount else 'EXIF',
            'white_balance': {'mode': 'manual', 'gains': (1 / np.array(m['asn'])).tolist(),
                              'AsShotNeutral': m['asn'], 'exif_white_balance': m['wb_exif'], 'record_0x26': m['wb_record_0x26'],
                              'temperature': None, 'compensation': None},
            'selector_bytes': {'recipe_slot': f['slot'], 'image_setting': m['selector'], 'raw13': m['raw13'],
                               'type26_control': 2 if f['slot'] == '04' else engine.entries[f['slot']]['control'],
                               'type26_control_source': 'official Standard=2 contract; recipe control from declared table; not observed from EXIF'},
            'source_kind': 'camera', 'color_space': 'sRGB' if color_space == 1 else 'unknown',
            'original_exif_color_space': color_space,
            'lens_id': None if mount else 'GR_LENS_A12_50mm_F2.5_MACRO',
            'lens_note': 'owner reports 35mm f/2; exact physical lens ID and ring aperture unknown' if mount else m.get('lens_model'),
            'corrections': {'peripheral_illumination': 'unknown', 'red_blue_shading': 'unknown', 'distortion': 'unknown'} if mount else {},
            'calibration_metadata_ready': not mount and color_space == 1,
            'hashes': f['hashes'], 'page': f['page'], 'capture_group': f['capture_group'],
            'recipe_assignment': f['assignment'], 'sampling': 'untrimmed native CFA mean and JPEG pixel mean; both spatial SDs retained',
        }
        H = np.array(f['geometry']['H'])
        geo = {'H': H, 'Hinv': np.linalg.inv(H)}
        for q in f['patches']:
            roi = chain.ar.roi_mask(geo, q['chart_roi_bbox'], rgb.shape)
            mean = None
            if roi is not None:
                ya, yb, xa, xb, mask, _ = roi
                mean = np.asarray(rgb[ya:yb, xa:xb], float)[mask].mean(axis=0).tolist()
            raw = q.get('raw', {})
            rows.append({'frame': f['frame'], 'page': f['page'], 'patch_id': q['patch_id'], 'class': q['class'],
                         'raw_rgb': raw.get('mean_cam'), 'jpeg_rgb': mean,
                         'valid': bool(q['valid'] and mean is not None),
                         'spatial_sd': {'raw_rgb': raw.get('sd'), 'jpeg_rgb': q.get('spatial_sd')},
                         'sample_key': q['sample_key'], 'flags': q['flags'],
                         'analyzer_trimmed_median_raw_rgb': q.get('raw_rgb'),
                         'analyzer_trimmed_median_jpeg_rgb': q.get('jpeg_rgb')})
    s.dump(out / 'frames.json', {'schema': 'ricoh-module-frames/1', 'frames': metadata,
        'metadata_complete': all(f['calibration_metadata_ready'] for f in metadata.values()),
        'unknown_metadata_is_not_imputed': True})
    with (out / 'patches.jsonl').open('w') as file:
        for row in rows:
            file.write(json.dumps(s.plain(row), ensure_ascii=False, allow_nan=False) + '\n')
    return {'frames': len(metadata), 'patches': len(rows), 'measurement_valid': sum(r['valid'] for r in rows),
            'ready_metadata_frames': sum(f['calibration_metadata_ready'] for f in metadata.values()),
            'sampling': 'means, conforming to EXCHANGE.md; scoring uses analyzer trimmed medians'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extraction', default='extraction')
    ap.add_argument('--mount', default='mount_repaired')
    ap.add_argument('--out', default='analysis')
    args = ap.parse_args()
    src, out = s.LOCAL / args.extraction, (s.LOCAL / args.out).resolve()
    assert out.is_relative_to(s.LOCAL) and not out.exists()
    analyzer, chain, p = s.setup(src, freeze=False)
    out.mkdir(parents=True)
    import analyzer_scoring as scoring
    frames = read_frames(src)
    repaired = {f['frame']: f for f in read_frames(s.LOCAL / args.mount)}
    frames = [repaired.get(f['frame'], f) for f in frames]
    # The owner explicitly rejected A after import. It has no identity, score, calibration, or validation role.
    excluded_a = [f'R805{n}' for n in range(1229, 1261)]
    frames = [f for f in frames if number(f) >= 1261]
    s.dump(out / 'manifest.json', {'schema': 'chart-v2-manifest/1', 'exclude': excluded_a,
        'frames': {stem: {'purpose': 'trial', 'reason': 'owner confirmed entire A group was photographed in error; exclude from all scoring, calibration and validation'} for stem in excluded_a}})
    failures = [f for f in frames if 'patches' not in f]
    frames = [f for f in frames if 'patches' in f]
    e = chain.model.Engine(s.TABLE, iso=200, provenance=p)
    # The owner sequence provides only a proposed 04 reference. Every C segment is challenged against all candidates.
    cbases = {f['page']: f for f in frames if 1270 <= number(f) <= 1275 and f['kind'] == 'screen'}
    identities = {}
    for f in frames:
        n = number(f)
        f['capture_group'] = 'A' if n <= 1260 else 'M' if n <= 1268 else 'C'
        if f['kind'] != 'screen' or f['capture_group'] == 'M':
            f['purpose'] = 'white' if f['kind'] == 'white' else 'screen'
            f['assignment'] = 'owner-native-Standard' if f['capture_group'] == 'M' else 'white-not-used-for-recipe-scores'
            if f['capture_group'] == 'M' and n == 1261:
                f['purpose'] = 'trial'
                f['assignment'] = 'native-Standard diagnostic P1 repeat at 1/80; main calibration set is six pages at 1/100'
            continue
        if f['page'] not in cbases:
            f['purpose'] = 'trial'
            f['assignment'] = 'trial-missing-C04-page'
            continue
        q = identity(f, cbases[f['page']], e)
        identities[f['frame']] = q
        f['slot'] = q['best_slot']
        f['purpose'] = 'screen' if q['reliable'] else 'trial'
        f['assignment'] = 'same-DNG-forward-model-vs-C04'
    # Pool independent pages within each proposed C segment; no fit and no target values enter identity assignment.
    groups = {}
    for slot, first in C_STARTS.items():
        group = [f for f in frames if first <= number(f) < first + 6]
        used = [identities[f['frame']] for f in group if f['frame'] in identities]
        errors = {slt: np.concatenate([q['_errors'][slt] for q in used]) for slt in SLOTS} if used else {}
        med = {k: stat(v) for k, v in errors.items()}
        ranked = sorted(med, key=lambda k: med[k]['median'] if med[k]['median'] is not None else float('inf'))
        best = ranked[0] if ranked else None
        confident = bool(best and med[best]['n'] >= 24 and med[best]['median'] <= 3 and
                         med[ranked[1]]['median'] - med[best]['median'] >= .35)
        groups[slot] = {'proposed_slot': slot, 'best_slot': best, 'pages': [f['page'] for f in group],
                       'frames': [f['frame'] for f in group], 'candidate_model_de00': med,
                       'confidence': 'high-pooled-pages' if confident else 'trial',
                       'sequence_confirmed': best == slot and confident}
        print(f"identity C {slot}: best={best} confident={confident} n={med[best]['n'] if best else 0}", flush=True)
        if confident:
            for f in group:
                f.update(slot=best, purpose='screen', assignment='C-six-page-pooled-forward-model')
    for f in frames:
        f['meta']['slot'] = f.get('slot')
        f['manifest'].update(slot=f['slot'], purpose=f['purpose']) if f.get('slot') else f['manifest'].update(purpose='trial')
    manifest = json.loads((out / 'manifest.json').read_text())
    manifest['frames'].update({f['frame']: {**f['manifest'], 'expected_page': f['page'], 'assignment': f['assignment']} for f in frames})
    s.dump(out / 'manifest.json', manifest)
    s.dump(out / 'identities.json', {'schema': 'chart-session-identities/1', 'C_segments': groups,
        'frames': {k: {kk: vv for kk, vv in q.items() if kk != '_errors'} for k, q in identities.items()},
        'A_group': 'excluded by owner; no recipe assignment or validation',
        'white_frames_unassigned': [f['frame'] for f in frames if f['kind'] == 'white'],
        'C04_anchor_is_owner_order_hypothesis': True})
    summaries = {}
    for group in ('C',):
        dest = out / ('scores_' + group)
        dest.mkdir()
        subset = [f for f in frames if f['capture_group'] == group]
        result = scoring.score_all(subset, chain, dest, table=s.TABLE)
        # Full six-page recipe coverage, rather than the old minimum P1/P4 shoot-list.
        result['session_full_coverage'] = {slot: sorted({f['page'] for f in subset if f.get('slot') == slot and f['kind'] == 'screen' and f['purpose'] != 'trial'}) for slot in SLOTS}
        extra = {}
        bins = []
        for slot in SLOTS:
            model_target, actual, baseline = [], [], []
            for f in subset:
                q = result['frames'].get(f['frame'])
                if not q or f['slot'] != slot:
                    continue
                keep = np.array(q['valid'], bool)
                md = e.fs.delta_e00(e.fs.lab_from_codes(q['model_rgb']), q['target_lab'])
                model_target.extend(md[keep]); actual.extend(np.array(q['de00'])[keep]); baseline.extend(np.array(q['baseline_de00'])[keep])
                b = next(x for x in subset if x['frame'] == q['matched04'])
                bx, _ = e.invert04(np.array([p['jpeg_rgb'] for p in b['patches']]), np.array([p['raw_wb'] for p in b['patches']]))
                x = bx * np.array([p['raw_wb'] for p in f['patches']]) / np.maximum(np.array([p['raw_wb'] for p in b['patches']]), 1e-9)
                lab = e.fs.lab_from_codes(e.predict('04', x))
                L, C = lab[:, 0], np.hypot(lab[:, 1], lab[:, 2])
                for lo, hi in ((0, 30), (30, 60), (60, 101)):
                    for clo, chi in ((0, 15), (15, 40), (40, 1000)):
                        m = keep & (L >= lo) & (L < hi) & (C >= clo) & (C < chi)
                        bins.append({'slot': slot, 'frame': f['frame'], 'page': f['page'], 'L_min': lo, 'L_max': hi,
                                     'C_min': clo, 'C_max': chi, 'values': np.array(q['de00'])[m].tolist(),
                                     'baseline_values': np.array(q['baseline_de00'])[m].tolist()})
            extra[slot] = {'predicted_vs_target': stat(model_target),
                           'predicted_similarity': chain.measure.similarity(model_target, baseline)}
        s.dump(dest / 'scores.json', result)
        s.dump(dest / 'model_comparison.json', extra)
        bins_summary = []
        for slot in SLOTS:
            for lo in (0, 30, 60):
                for clo in (0, 15, 40):
                    matches = [b for b in bins if b['slot'] == slot and b['L_min'] == lo and b['C_min'] == clo]
                    dd = [v for b in matches for v in b['values']]; bb = [v for b in matches for v in b['baseline_values']]
                    bins_summary.append({'slot': slot, 'L_min': lo, 'C_min': clo, **stat(dd), 'similarity': chain.measure.similarity(dd, bb)})
        s.dump(dest / 'lightness_chroma.json', {'coordinates': 'matched04 model response Lab D65', 'bins': bins_summary})
        summaries[group] = result
        print(f"scores {group}: {result['status']} errors={len(result['errors'])}", flush=True)
    stability = scoring.stability_report([f for f in frames if f['capture_group'] == 'C'], chain)
    stability['Mount'] = scoring.stability_report([f for f in frames if f['capture_group'] == 'M'], chain)
    whites = []
    wf = [f for f in frames if f['kind'] == 'white']
    for f in wf:
        q = f['patches'][0]
        whites.append({'frame': f['frame'], 'group': f['capture_group'], 'selector': f['meta']['selector'],
                       'raw_rgb': q['raw_rgb'], 'jpeg_rgb': q['jpeg_rgb'], 'flags': q['flags']})
    stability['white_pages'] = whites
    stability['white_page_note'] = 'RAW can diagnose illumination drift; JPEG whites cross recipe and selector states and are not neutral control repeats'
    s.dump(out / 'stability.json', stability)
    exclusion_rows = []
    for f in frames:
        score = summaries.get(f['capture_group'], {}).get('frames', {}).get(f['frame'])
        for i, q in enumerate(f['patches']):
            if q['flags'] or (score and not score['valid'][i]):
                exclusion_rows.append({'frame': f['frame'], 'group': f['capture_group'], 'slot': f.get('slot'),
                    'page': f['page'], 'patch_id': q['patch_id'], 'sample_key': q['sample_key'],
                    'measurement_flags': q['flags'], 'score_excluded': bool(score and not score['valid'][i]),
                    'score_extra_reason': 'paired04-quality / inverse-domain / target-support' if score and not score['valid'][i] and not q['flags'] else None})
    write_csv(out / 'excluded_patches.csv', exclusion_rows, ['frame', 'group', 'slot', 'page', 'patch_id', 'sample_key', 'measurement_flags', 'score_excluded', 'score_extra_reason'])
    # Exchange keeps the EXCHANGE.md mean estimator, separate from the frozen scoring estimator.
    exchange50 = [f for f in frames if f['unit'] == 'a12-50' and f['kind'] == 'screen' and f['purpose'] != 'trial']
    exchangem = [f for f in frames if f['unit'] == 'mount-a12' and f['kind'] == 'screen' and f['purpose'] != 'trial']
    exchange = {'50mm': export_exchange(exchange50, out / 'exchange/50mm', analyzer, chain, e),
                'mount': export_exchange(exchangem, out / 'exchange/mount', analyzer, chain, e)}
    targets = []
    for frameid, q in summaries['C']['frames'].items():
        f = next(f for f in frames if f['frame'] == frameid)
        if f['slot'] == '04':
            continue
        for i, patch in enumerate(f['patches']):
            if q['valid'][i]:
                targets.append({'page': f['page'], 'patch_id': patch['patch_id'], 'slot': f['slot'],
                                'target_lab': q['baseline_target_lab'][i], 'baseline_target_lab': q['baseline_target_lab'][i],
                                'baseline_frame': q['matched04'], 'source_recipe_frame': frameid})
    s.dump(out / 'exchange/50mm/targets_for_04.json', {'schema': 'ricoh-module-targets/1', 'whitepoint': 'D65',
        'source': 'C matched04 DNG-conditioned targets from frozen closed_loop target definitions; 01/02 relative GR surrogate, 03 empirical GR IV HC, 05/06 official Fuji LUT; no new fit', 'samples': targets})
    s.dump(out / 'exchange_summary.json', exchange)
    rows = []
    for f in frames:
        q = identities.get(f['frame'], {})
        rows.append({'frame': f['frame'], 'group': f['capture_group'], 'page': f['page'], 'kind': f['kind'],
                     'slot': f.get('slot'), 'purpose': f['purpose'], 'assignment': f['assignment'],
                     'identity_confidence': q.get('confidence'), 'best_slot': q.get('best_slot'),
                     'gap_de00': q.get('gap_de00'), 'identity_n': q.get('n'), 'shutter_s': f['meta']['t'],
                     'aperture_f': f['meta']['f'], 'measurement_valid': f['valid_patches'],
                     'total_patches': len(f['patches']), 'page_confidence': f['identification']['confidence']})
    write_csv(out / 'frame_assignments.csv', rows, list(rows[0]))
    s.dump(out / 'frame_assignments.json', rows)
    s.dump(out / 'extraction_failures.json', failures)
    for f in frames:
        s.dump(out / 'frames' / (f['frame'] + '.json'), f)
    from quality_session import render
    render(out, frames, analyzer, summaries['C'], stability)
    s.dump(out / 'provenance.json', p.finish())
    print(json.dumps(exchange, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
