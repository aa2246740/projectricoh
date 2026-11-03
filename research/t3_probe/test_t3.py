#!/usr/bin/env python3
"""Synthetic recovery, negative controls, JPEG+DNG extraction and real-frame dry runs."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location('t3_analyzer_tests', Path(__file__).with_name('analyze_t3.py'))
a = importlib.util.module_from_spec(sp); sp.loader.exec_module(a)
p, m = a.p, a.m
import numpy as np
from PIL import Image


def setup():
    f = m.calibration()
    e = m.Engine(f[0]['meta']['display'])
    report = json.loads((p.LOCAL / 'predictions.json').read_text())
    pred = {k: np.array(v) for k, v in report['delta'].items()}
    return e, f, report, pred, np.array(report['weights'])


def arrays(e, frames, report, predictions, weights):
    base = .5 * (frames[0]['rgb'] + frames[1]['rgb'])
    repeat = frames[1]['rgb'] - frames[0]['rgb']
    rng = np.random.default_rng(20261021)
    cases = []
    for key, _, _ in m.HYPOTHESES:
        joint, sector, weak = 0, 0, 0
        for _ in range(30):
            # Keep the RGB channel correlation, randomize patch locations and signs.
            noise = repeat[rng.permutation(155)] * rng.choice([-1, 1], (155, 1))
            v = a.score_arrays(e, frames[0]['rgb'], base + predictions[key] + noise,
                               frames[1]['rgb'], predictions, weights)
            joint += v['joint_best']['hypothesis'] == key
            compatible = True
            for s in m.SECTORS:
                mask = e.ring & (weights[:, s] >= .1)
                expected = next(g for g in a.equivalent_groups(predictions, mask) if key in g)
                compatible &= bool(set(v['sectors'][str(s)]['best_fixed_hypotheses']) & set(expected))
                weak += v['sectors'][str(s)]['status'] == 'weak_separation'
            sector += compatible
        p.require(joint == 30, f'Joint synthetic recovery {key}: {joint}/30')
        # Keep per-sector counts honest. No false unique claim for equal templates.
        cases.append({'hypothesis': key, 'trials': 30, 'joint_recovered': joint,
                      'both_sector_equivalence_groups_recovered': sector, 'weak_sector_verdicts': weak})
    nochange = a.score_arrays(e, frames[0]['rgb'], frames[0]['rgb'], frames[1]['rgb'], predictions, weights)
    p.require(nochange['result'] == 'no_effect' and nochange['joint_best']['hypothesis'] == 'H0', 'No-change false acceptance')
    bad = frames[1]['rgb'].copy(); bad[e.grey, 0] += 8
    restored = a.score_arrays(e, frames[0]['rgb'], base + predictions['H1'], bad, predictions, weights)
    p.require(restored['result'] == 'abnormal', 'Bad restore accepted')
    localized = a.score_arrays(e, frames[0]['rgb'], base + predictions['H1'],
                               frames[1]['rgb'] + predictions['H1'], predictions, weights)
    p.require(localized['result'] == 'abnormal' and not localized['04_restore']['pass'],
              'Persistent local colour change in returned 04 falsely accepted')
    badmeta = a.score_arrays(e, frames[0]['rgb'], base + predictions['H1'], frames[1]['rgb'],
                             predictions, weights, {'pass': False, 'errors': ['ISO mismatch']})
    p.require(badmeta['result'] == 'abnormal', 'Bad metadata accepted')
    corrupted = base + predictions['H1']
    controls = e.ring & (weights[:, list(m.SECTORS)].sum(1) < 1e-6)
    corrupted[controls, 0] += 15
    control = a.score_arrays(e, frames[0]['rgb'], corrupted, frames[1]['rgb'], predictions, weights)
    p.require(control['result'] == 'abnormal', 'Changes outside the modified sectors accepted')
    continuous = a.score_arrays(e, frames[0]['rgb'], base + predictions['H1'] * 1.4,
                                frames[1]['rgb'], predictions, weights)
    p.require(all(abs(r['candidate_scale_fit']['scale'] - 1.4) < 1e-8 for r in continuous['sectors'].values()),
              'Continuous scale not measured')
    old = p.legacy_analyzer()
    meta_cases = []
    for field, value in (('iso', 1600), ('selector', 3), ('t', 1/500), ('f', 5.6),
                         ('wb_record_0x26', 0), ('asn', [.7, 1., .9]), ('program', 2), ('exposure_mode', 0)):
        fs = [{'meta': copy.deepcopy(frames[0]['meta']), 'metadata_errors': []} for _ in range(3)]
        fs[1]['meta'][field] = value
        p.require(not old.metadata_checks(fs)['pass'], 'Metadata accepted: ' + field)
        meta_cases.append(field)
    for outside in (p.ROOT / 'research/outside-t3', p.SCRATCH):
        try:
            a.output_path(outside)
        except ValueError:
            pass
        else:
            raise AssertionError('Output fence accepted outside path')
    # Independent artificial two-input/one-output checks, unrelated to firmware bytes.
    ci = np.array([32+64j, -64+32j])
    original_weights = e.weights
    e.weights = lambda hue: np.ones((len(hue), 24))
    try:
        literal = {
            (11, 'candidate'): [[2.804, -1.428272, 0.], [1.402, -.714136, 0.]],
            (17, 'candidate'): [[1.402, -.714136, 0.], [-2.804, 1.428272, 0.]],
            (17, 'transpose'): [[0., -.688272, 3.544], [0., -.344136, 1.772]],
        }
        for (s, layout), expected in literal.items():
            p.require(np.allclose(e.basis(ci, s, layout), expected, atol=1e-6), 'Independent coefficient mapping check')
    finally:
        e.weights = original_weights
    p.require(m.signmag(0x80) == 0 and m.signmag(0x82) == -2 and m.encode(-2) == 0x82, 'Sign magnitude semantics')
    result = {'cases': cases, 'trials': len(cases) * 30, 'joint_recovered': sum(q['joint_recovered'] for q in cases),
              'no_change': nochange['result'], 'bad_restore': restored['result'],
              'localized_bad_restore': localized['result'], 'bad_metadata': badmeta['result'],
              'unmodified_sector_change': control['result'],
              'continuous_scale_1_4_recovered': True, 'metadata_rejections': meta_cases,
              'output_fence': True, 'independent_literal_mapping_checks': 3, 'sign_magnitude': True}
    p.dump(p.LOCAL / 'tests/arrays.json', result, private=True)
    print(f'array joint recovery {len(cases)*30}/{len(cases)*30}; no-change, restore, metadata, control sectors, scale and mapping checks PASS')


def synthetic(e, frames, key, delta, index):
    folder = p.LOCAL / 'tests/images' / key
    source = p.CAP / 'R8051179.JPG'
    im = Image.open(source)
    image = np.array(im.convert('RGB'), dtype=float)
    H = frames[0]['H']; geo = {'H': H, 'Hinv': np.linalg.inv(H)}
    # Inject an exactly known independent constant dRGB into real chart patch pixels.
    # Two 04 frames bracket it, so add half their drift to the source frame.
    drift = .5 * (frames[1]['rgb'] - frames[0]['rgb'])
    for i, patch in enumerate(e.layout['patches']):
        ya, yb, xa, xb, mask, _ = e.ar.roi_mask(geo, patch['bbox_px'], image.shape)
        block = image[ya:yb, xa:xb]
        block[mask] = np.clip(block[mask] + delta[i] + drift[i], 0, 255)
    folder.mkdir(parents=True, exist_ok=True)
    jpg, dng = folder / 'probe.JPG', folder / 'probe.DNG'
    Image.fromarray(np.rint(image).astype(np.uint8)).save(jpg, quality=98, subsampling=0, exif=im.info['exif'])
    shutil.copyfile(source.with_suffix('.DNG'), dng)
    p.ignored(jpg); p.ignored(dng)
    return jpg


def images(e, frames, predictions, indices):
    for i in indices:
        key = m.HYPOTHESES[i][0]
        jpg = synthetic(e, frames, key, predictions[key], i)
        v, text = a.analyze([p.CAP/'R8051179.JPG', jpg, p.CAP/'R8051182.JPG'],
                            p.LOCAL/'tests/image_results'/key, e)
        p.require(v['joint_best']['hypothesis'] == key, f'Image recovery: {key} -> {v["joint_best"]["hypothesis"]}')
        p.require(v['metadata_checks']['pass'] and v['04_restore']['pass'] and v['control_patches']['pass'],
                  'Synthetic image checks failed: ' + key)
        expected = 'no_effect' if key == 'H0' else 'compatible'
        p.require(v['result'] == expected, 'Synthetic image verdict: ' + key + ' -> ' + v['result'])
        print(f"image {key}: {v['result']}, joint residual {v['joint_best']['residual_RMS_codes']:.3f} codes")


def dry_run(e, full=False):
    # 1180/1181 are historical hue-ring calibration probes, not new T3/T1 captures.
    # This verifies the real file/metadata/geometry path; it cannot accept the new package.
    names = ['R8051179.JPG', 'R8051180.JPG', 'R8051182.JPG']
    if full:
        names += ['R8051181.JPG', 'R8051182.JPG']
    v, text = a.analyze([p.CAP/q for q in names], p.LOCAL/'tests'/('dry_full' if full else 'dry_real'), e)
    p.require(v['metadata_checks']['pass'], 'Historical real-frame metadata path failed')
    p.require(v['result'] != 'compatible', 'Historical different probe falsely accepted')
    if full:
        p.require('probe2' in v and 'probe2_delegation' in v, 'Full sequence did not call existing probe2 analyzer')
    print(text, end='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arrays', action='store_true')
    parser.add_argument('--images', nargs='*', type=int)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--nochange', action='store_true')
    parser.add_argument('--full-synthetic', action='store_true')
    args = parser.parse_args()
    p.preflight()
    e, f, report, pred, weights = setup()
    if args.arrays:
        arrays(e, f, report, pred, weights)
    if args.images is not None:
        indices = args.images or list(range(len(m.HYPOTHESES)))
        p.require(all(0 <= i < len(m.HYPOTHESES) for i in indices), 'Bad hypothesis index')
        images(e, f, pred, indices)
    if args.dry_run:
        dry_run(e, args.full)
    if args.full_synthetic:
        paths = [p.CAP/'R8051179.JPG', p.LOCAL/'tests/images/H1/probe.JPG', p.CAP/'R8051182.JPG',
                 p.ROOT/'research/t1_probe/probe2/local/tests/images/absolute_BCD/probe.JPG', p.CAP/'R8051182.JPG']
        v, text = a.analyze(paths, p.LOCAL/'tests/full_synthetic', e)
        p.require(v['result'] == 'compatible' and v['joint_best']['hypothesis'] == 'H1', 'Full synthetic T3 rejected')
        p.require(v['probe2']['result'] == 'functional_pass' and
                  v['probe2']['best_hypothesis']['id'] == 'absolute_BCD', 'Full synthetic 08 not handed to probe2 correctly')
        print(text, end='')
    if args.nochange:
        v, text = a.analyze([p.CAP/'R8051179.JPG', p.CAP/'R8051179.JPG', p.CAP/'R8051182.JPG'],
                            p.LOCAL/'tests/no_change', e)
        p.require(v['result'] == 'no_effect', 'Real no-change false acceptance')
        print(text, end='')


if __name__ == '__main__':
    main()
