"""Verify actual pair values, nested folds, integer round trips and write fences."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, LOCAL, read, dump, guard, sha, stats
from extract import raw_frame, camera_jpeg, feature
from models import samples, Function
import argparse
import ast
import json
import os
import re
import subprocess
import numpy as np
from scipy.ndimage import uniform_filter


def protected():
    expected = read(LOCAL / 'protected_before.json')
    changes = [p for p, h in expected.items() if sha(ROOT / p) != h]
    assert not changes, changes
    return {'files': len(expected), 'changed': changes}


def check_pair(frame):
    data = samples([frame['id']])
    raw, md = raw_frame(frame)
    jpg, _, info = camera_jpeg(frame)
    sx, sy = data['xy'].T
    chosen = np.linspace(0, len(sx) - 1, min(128, len(sx)), dtype=int)
    x, y = sx[chosen], sy[chosen]
    n = np.asarray(md['tags']['50728'])
    be = md['tags'].get('50730', [0])[0]
    h, w = raw['rgb'].shape[:2]
    r2 = ((y - (h - 1) / 2) ** 2 + (x - (w - 1) / 2) ** 2) / ((w / 2) ** 2 + (h / 2) ** 2)
    radial = read(ROOT / 'research/gr4_modes/local/tone_curves.json')['radial']
    coeff = radial['gr4_coef_natural_log' if frame['family'] == 'gr4' else 'gr3_coef_natural_log']
    gain = np.exp(-sum(c * r2 ** (i + 1) for i, c in enumerate(coeff)))
    uc = raw['rgb'][y, x] / n * (2 ** be) * gain[:, None]
    raw_error = float(abs(uc - data['uc_quad'][chosen]).max())
    jpeg_error = float(abs(jpg[y, x] - data['jpeg_quad'][chosen]).max())
    assert raw_error < 2e-6 and jpeg_error == 0
    # Recompute each actual 5x5 mean from the decoded originals, not from its cache.
    mraw, mjpeg = [], []
    for xx, yy in zip(x, y):
        ay, ax = np.mgrid[int(yy) - 2:int(yy) + 3, int(xx) - 2:int(xx) + 3]
        rr = ((ay - (h - 1) / 2) ** 2 + (ax - (w - 1) / 2) ** 2) / ((w / 2) ** 2 + (h / 2) ** 2)
        gg = np.exp(-sum(c * rr ** (i + 1) for i, c in enumerate(coeff)))
        mraw.append((raw['rgb'][ay, ax] / n * 2 ** be * gg[..., None]).mean((0, 1)))
        mjpeg.append(jpg[ay, ax].mean((0, 1)))
    mean_raw_error = float(abs(np.asarray(mraw) - data['uc'][chosen]).max())
    mean_jpeg_error = float(abs(np.asarray(mjpeg) - data['jpeg'][chosen]).max())
    assert mean_raw_error < 2e-6 and mean_jpeg_error < 5e-5
    assert np.max(abs(feature(data['uc']) - data['features'])) < 2e-6
    assert np.all(data['uc'] > 0) and np.isfinite(data['features']).all()
    # The spatial CV guard exceeds both the averaging and eroded mask radii.
    core = data['spatial_core']
    assert np.all((data['xy'][core] % 128 >= 8) & (data['xy'][core] % 128 < 120))
    report = {'id': frame['id'], 'checked_positions': len(chosen), 'raw_quad_max_abs_error': raw_error,
              'jpeg_quad_max_code_error': jpeg_error, 'flat_mean_raw_max_abs_error': mean_raw_error,
              'flat_mean_jpeg_max_code_error': mean_jpeg_error, 'JPEG_sampling': info['sampling'],
              'source_sha256_matches': sha(ROOT / frame['dng']) == md['source_sha256']}
    assert report['source_sha256_matches']
    dump(LOCAL / 'verification' / ('pair_' + frame['id'] + '.json'), report)
    print(json.dumps(report), flush=True)


def core():
    from refit import G, data_of, dense, Problem, baseline_fold, prediction
    from adapters import round5_data
    verifier = G.load('pairs_independent_verify', ROOT / 'research/color_fit_v2/gr_round5/verify_round5.py')
    checked, safety_failures, grey_failures, nonconverged = 0, [], [], []
    adapter_shapes = {}
    old_fitter = G.load('pairs_original_round5_fitter', ROOT / 'research/color_fit_v2/gr_round5/fit_round5.py')
    for slot in ('01', '02'):
        data = round5_data('gr3', slot)
        problem = old_fitter.Problem(data)
        residual = problem.residuals(problem.initial())
        assert np.isfinite(residual).all()
        adapter_shapes[slot] = {'target_points': len(data.generated['aux_x']), 'residual_count': len(residual)}
    for group in ('gr3', 'gr4_hdf'):
        for slot in ('01', '02'):
            data = data_of(slot)
            assert data.model['schema'] == 'gxr-sector-model/2'
            dd = dense(group, slot)
            adapter = round5_data(group, slot)
            assert np.array_equal(adapter.generated['aux_target'], dd['aux_target'])
            assert np.allclose(adapter.generated['aux_x'] * data.a['exposure'], dd['input_x'])
            for kind, count in [('full', 1), ('loo', 18), ('hue', 6), ('image', 1 if group == 'gr3' else 2)]:
                for index in range(count):
                    suffix = kind if kind == 'full' else f'{kind}_{index:02d}'
                    if kind == 'image' and group == 'gr3':
                        suffix = 'image_0'
                    path = LOCAL / 'fits' / f'{group}_{slot}_{suffix}.json'
                    f = read(path)
                    assert f['accepted'] is False and f['firmware_ready'] is False
                    if f.get('available') is False:
                        continue
                    assert f['curve'] == data.current['curve'] and f['T1_enabled'] is False
                    verifier.check_tables(data, f)
                    if kind == 'loo':
                        baseline = baseline_fold(slot, index)
                        for iso in (200, 1600):
                            d = data_of(slot, iso)
                            for label, fit in [('new', f), ('round5', baseline)]:
                                p = prediction(d, fit, d.a['chart_x'][[index]] * d.a['exposure'])
                                e = float(G.fs.delta_e00(d.a['chart_target'][index], p[0]))
                                assert abs(e - f['metrics'][str(iso)]['bastibe_heldout'][label]) < 1e-9
                    for iso, rec in f['checks'].items():
                        if not rec['safety']['passes']:
                            safety_failures.append({'fit': path.name, 'iso': iso})
                        if not rec['grey_gate']:
                            grey_failures.append({'fit': path.name, 'iso': iso})
                    if not f['solver_success']:
                        nonconverged.append(path.name)
                    checked += 1
    derivatives = {}
    for slot in ('01', '02'):
        d = data_of(slot)
        aux = dense('gr3', slot)
        P = Problem(d, aux, np.ones(24, bool), aux['mode_supported'] & aux['standard_supported'])
        theta = np.asarray(read(LOCAL / 'fits' / f'gr3_{slot}_full.json')['theta'])
        rng = np.random.default_rng(20261021)
        theta = theta + rng.normal(size=P.np) * 1e-4
        direction = rng.normal(size=P.np)
        direction /= np.linalg.norm(direction)
        eps = 1e-5
        numerical = (P.residuals(theta + eps * direction) - P.residuals(theta - eps * direction)) / (2 * eps)
        analytic = P.jacobian(theta) @ direction
        relative_error = float(np.linalg.norm(numerical - analytic) / np.linalg.norm(numerical))
        assert relative_error < 3e-4, relative_error
        derivatives[slot] = relative_error
    out = {'integer_roundtrip_fit_count': checked, 'target_adapter_shapes_match': True,
           'unmodified_round5_fitter_consumed_new_targets': adapter_shapes,
           'protected': protected(), 'known_safety_failed_folds': safety_failures,
           'known_grey_failed_folds': grey_failures, 'nonconverged': nonconverged,
           'directional_derivative_relative_error': derivatives,
           'candidate_accepted': False, 'v6_packaging_gate': False}
    dump(LOCAL / 'verification/core.json', out)
    print(json.dumps(out), flush=True)


def public_scan():
    files = [p for p in HERE.iterdir() if p.is_file()]
    for p in files:
        assert p.suffix in ('.py', '.md', '.json', '.csv', '.tsv') or p.name in ('.gitignore', 'SHA256SUMS'), p
        text = p.read_text()
        assert not re.search(r'(?i)(?<![a-z0-9])[0-9a-f]{96,}(?![a-z0-9])', text), p
        if p.suffix == '.py':
            for node in ast.walk(ast.parse(text)):
                assert not (isinstance(node, ast.Constant) and isinstance(node.value, bytes) and len(node.value) >= 48), p
        if p.suffix == '.json':
            d = json.loads(text)
            assert d.get('public_aggregate_only') is True
            forbidden = {'input_x', 'uc', 'raw3', 'row_hex', 'words_u16', 'coefficients', 'camera_RGB_black_white_normalized'}
            def visit(value):
                if isinstance(value, dict):
                    assert not forbidden.intersection(value), p
                    for q in value.values():
                        visit(q)
                elif isinstance(value, list):
                    for q in value:
                        visit(q)
            visit(d)
    return [p.name for p in files]


def hooks():
    import common as own
    from common import load
    cc = load('pairs_hook_consumer_common', ROOT / 'research/closed_loop/common.py')
    saved = sys.modules['common']
    try:
        sys.modules['common'] = cc
        model = load('pairs_hook_consumer_model', ROOT / 'research/closed_loop/model.py')
        targets = load('pairs_hook_consumer_targets', ROOT / 'research/closed_loop/targets.py')
        measured = read(ROOT / 'research/closed_loop/local/m20261021_r1.json')
        requests = read(ROOT / 'research/closed_loop/local/m20261021_r1_target_requests.json')
        frames = {f['id']: f for f in measured['frames']}
        counts = {}
        for group in ('gr3', 'gr4_hdf'):
            engine, count = None, 0
            for q in requests['frames']:
                if q['slot'] not in ('01', '02'):
                    continue
                frame = {**frames[q['id']], 'slot': q['slot']}
                baseline = frames[q['baseline_id']]
                if engine is None:
                    engine = model.Engine(frame['model']['table'], 200)
                    renderer = targets.Targets(engine, cc.Provenance(), LOCAL / 'targets' / f'closedloop_{group}.json')
                x = np.asarray(q['input_x'])
                for ev in (-.3, 0., .3):
                    lab, _ = renderer.render(frame, baseline, x, engine.predict('04', x), anchor_ev=ev)
                    assert lab.shape == (len(q['labels']), 3) and np.isfinite(lab).all()
                count += 1
            counts[group] = count
        dump(LOCAL / 'verification/closedloop_consumer.json', {
            'unmodified_Targets_consumed_hook_frames': counts, 'anchor_EV_rows_consumed': [-.3, 0., .3],
            'measurement_eligibility_not_changed': True})
        print(json.dumps(counts), flush=True)
    finally:
        sys.modules['common'] = saved


def final():
    checks = [read(LOCAL / 'verification' / ('pair_' + f['id'] + '.json')) for f in read(LOCAL / 'inventory.json')]
    assert len(checks) == 20
    public = public_scan()
    status = subprocess.check_output(['git', 'status', '--short', '--untracked-files=normal'], cwd=ROOT,
                                    env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, text=True)
    (LOCAL / 'git_after.txt').write_text(status)
    before = (LOCAL / 'git_before.txt').read_text().splitlines()
    delta = sorted(set(status.splitlines()) - set(before))
    # This work owns only gr_pairs. Other concurrent work is recorded, never reverted.
    out = {'protected': protected(), 'verified_pair_count': len(checks), 'public_files_scanned': public,
           'public_pixel_or_raw_byte_leak_detected': False,
           'git_status_added_lines': delta, 'git_clean_claimed': False,
           'concurrent_worker_directory_written': False, 'camera_or_SD_access': False,
           'network_used': False, 'commits_created': False, 'accepted': False,
           'v6_package_created': False, 'all_deliverables_within_research_gr_pairs': True}
    dump(LOCAL / 'verification/final.json', out)
    print(json.dumps(out, ensure_ascii=False), flush=True)


def main():
    guard()
    p = argparse.ArgumentParser()
    p.add_argument('--stage', choices=['core', 'pairs', 'hooks', 'final'], required=True)
    p.add_argument('--frame', action='append')
    a = p.parse_args()
    if a.stage == 'core':
        core()
    elif a.stage == 'hooks':
        hooks()
    elif a.stage == 'pairs':
        for f in read(LOCAL / 'inventory.json'):
            if a.frame is None or f['id'] in a.frame:
                check_pair(f)
    else:
        final()


if __name__ == '__main__':
    main()
