"""Check the actual numeric tables, masks, model lock, and research boundary."""
from pathlib import Path
import argparse
import copy
import json
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
import fit


def numeric_checks():
    results = {}
    original = rt.read('research/gr_complete_pipeline/gr3_gr4_effective_curves.json')
    errors = []
    for row in original['effective_curves']:
        if row['model'] != 'gr4' or row['mode'] == 'HighContrastBW': continue
        mode = {'Standard': 'standard', 'PositiveFilm': 'positive', 'NegativeFilm': 'negative'}[row['mode']]
        errors.append(int(abs(sim.gamma14(mode, row['gain']) - row['curve_u16_256']).max()))
    assert len(errors) == 6 and max(errors) == 0
    results['gamma14_source_states'] = len(errors)
    original_front = rt.read('research/gr_complete_pipeline/arm_color_math_verification.json')['models']['gr4']
    names = {'standard': 'Standard', 'positive': 'Positive Film', 'negative': 'Negative Film'}
    for mode in sim.MODES:
        prior = np.asarray(sim.parameters()['modes'][mode]['sensor']).reshape(3, 3) / 8192
        front = sim.front_matrix(mode, dict(matrix_base=prior), sim.Options(front='integer')) * 256
        assert np.array_equal(front, original_front[names[mode]]['front'])
        assert np.array_equal(front.sum(axis=1), [256, 256, 256])
    results['integer_front_source_states'] = 3
    nwords = 0
    folder = rt.LOCAL / 'numeric_tables'
    folder.mkdir(exist_ok=True)
    for mode in sim.MODES:
        for gain in (4096, 8192, 11222, 24576):
            source = sim.gamma14(mode, gain)
            nodes = np.minimum(source >> 4, 1023)
            x, table = sim.gamma_table(mode, gain, 'increments')
            words = []
            decoded = []
            for i in range(256):
                delta = max(0, min(240, int(nodes[min(i + 1, 255)] - nodes[i])))
                word, last, current = 0, 0, int(nodes[i])
                values = [current]
                for k in range(1, 16):
                    point = k * delta // 16
                    change = point - last
                    assert 0 <= change <= 15
                    word |= change << (k * 4)
                    last = point
                for k in range(1, 16):
                    current += (word >> (k * 4)) & 15
                    values.append(current)
                words.append(word); decoded.extend(values)
            assert len(decoded) == 4096 and np.array_equal(np.rint(table * 1023).astype(int), decoded)
            assert np.array_equal(np.asarray(decoded)[::16], nodes)
            assert all(int(nodes[-1]) == int(v) for v in decoded[-16:])
            assert table.min() >= 0 and table.max() <= 1 and np.diff(table).min() >= 0
            blob_nodes, blob_steps = struct.pack('<256H', *nodes), struct.pack('<256Q', *words)
            assert len(blob_nodes) == 512 and len(blob_steps) == 2048
            (folder / f'{mode}_{gain}_nodes.bin').write_bytes(blob_nodes)
            (folder / f'{mode}_{gain}_increments.bin').write_bytes(blob_steps)
            nwords += len(words)
    results['gamma_increment_words_roundtripped'] = nwords
    state = rt.read(rt.LOCAL / 'calibration/P2.json')
    common, options = state['common'], sim.Options(**state['options'])
    values = np.array([[0, 0, 0], [.01, .02, .03], [.18, .18, .18], [.7, .2, .1], [1., 1., 1.]])
    assert np.array_equal(sim.multiaxial(values, 'negative', options), values)
    for mode in sim.MODES:
        default = sim.parameters()['modes'][mode]['sliders']
        a, b = sim.render(values, mode, common, options), sim.render(values, mode, common, options, default)
        assert np.array_equal(a, b)
        assert np.isfinite(a).all() and a.min() >= 0 and a.max() <= 1
    results['negative_ma_disabled_unchanged'] = True
    results['explicit_default_sliders_equal_default_path'] = True
    for name in ('knots', 'poly3', 'poly_center'):
        p, _ = fit.initial(name)
        c = fit.common_of(p, 8192, name); c.update(fit.metadata())
        assert np.array_equal(sim.source_gain([.2, .8], None, c), [1., 1.])
        assert np.allclose(sim.source_gain([.2, .8], c['chart_sources'][0], c), sim.radial_gain([.2, .8], c))
    raw = values.copy()
    be = np.array([-.5, .5, 0., -.25, .75])
    mapping = np.asarray(common['raw_wb_to_scene']) / 2 ** common['template_baseline_exposure']
    scene = raw @ mapping.T * 2 ** be[:, None]
    camera = raw * 2 ** (be - common['template_baseline_exposure'])[:, None]
    for mode in sim.MODES:
        assert np.max(abs(sim.render_scene(scene, mode, common, options) - sim.render(camera, mode, common, options))) < 1e-12
    results['baseline_exposure_once_camera_scene_parity'] = True
    return results


def isolation_check():
    a = rt.arrays(rt.LOCAL / 'dense.npz')
    changed = {k: v.copy() for k, v in a.items()}
    changed['positive'][:] = .97
    changed['negative'][:] = .03
    for key in ('standard', 'raw_wb', 'radius', 'xy'):
        changed[key][changed['band'] == 4] = np.nan
    first, second = fit.training_data(a), fit.training_data(changed)
    assert all(np.array_equal(first[k], second[k]) for k in first)
    selected = rt.read(rt.LOCAL / 'calibration/P0.json')
    left = fit.fit_data(first, selected['kind'], selected['loss'], sim.Options(),
        gains=[selected['common']['gain']], refine_gain=False, tag='isolation_original')
    right = fit.fit_data(second, selected['kind'], selected['loss'], sim.Options(),
        gains=[selected['common']['gain']], refine_gain=False, tag='isolation_changed')
    assert rt.plain(left) == rt.plain(right)
    rt.dump('isolation_calibration.json', left)
    return dict(style_and_outer_values_replaced=True, same_training_rows=True,
        single_gain_calibration_identical=True, same_row_count=len(first['raw_wb']))


def acceptance_checks():
    lock = rt.read(rt.LOCAL / 'model_lock.json')['files']
    assert all(rt.sha(rt.HERE / name) == value for name, value in lock.items())
    a = rt.arrays(rt.LOCAL / 'dense.npz')
    scores = rt.read(rt.LOCAL / 'scores.json')
    stages = ('r1_reference', 'P0_source_only', 'P0', 'P1_front_fixed', 'P1_nodes_fixed',
        'P1_increments_fixed', 'P1_all_fixed', 'P1', 'P2_native_fixed', 'P2')
    expected = {}
    for mode in sim.MODES:
        use = (a['band'] == 4) & a[mode + '_valid'] & np.isin(a['role'], ['colour', 'tone', 'reference', 'natural'])
        expected[mode] = int(use.sum())
        for stage in stages:
            rows = [r for r in scores if r['model'] == stage and r['dataset'] == 'dense' and r['split'] == 'held_page4' and r['mode'] == mode]
            assert len(rows) == 1 and rows[0]['n'] == expected[mode]
            predicted = rt.arrays(rt.LOCAL / ('predictions_' + stage + '.npz'))[mode]
            actual_median = float(np.median(rt.de(predicted[use], a[mode][use])))
            assert actual_median == rows[0]['median']
    baseline = rt.arrays('research/gr4_analytic_target_r1/local/predictions_primary_pre_hard.npz')
    replay = rt.arrays(rt.LOCAL / 'predictions_r1_reference.npz')
    parity = max(float(np.max(abs(baseline[m] - replay[m]))) for m in sim.MODES)
    assert parity < 1e-12
    gate = rt.read(rt.LOCAL / 'gate.json')
    assert gate['accepted'] == all(r['dense_median'] <= gate['threshold'] for r in gate['checks'])
    if not gate['accepted']:
        assert not list(rt.LOCAL.rglob('*448*'))
        assert not (rt.LOCAL / 'candidates').exists()
    audits = rt.read(rt.LOCAL / 'new_samples_audit.json')
    assert len(audits) == 3 and all(not r['used_for_fit_or_selection'] for r in audits)
    assert [r['samples'] for r in audits] == [51, 74, 95]
    assert all(r['baseline_exposure_applications'] == 1 for r in audits)
    return dict(model_lock_files=len(lock), unchanged_outer_support=expected,
        primary_medians_recomputed_from_arrays=True, reference_maximum_rgb_difference=parity,
        candidate_condition_consistent=True, new_holdout_frames=3, new_holdout_rois=220)


def input_check():
    changed = [name for name, value in list(rt.INPUTS.items()) if rt.sha(rt.ROOT / name) != value]
    assert not changed, changed
    ignored = subprocess.run(['git', 'check-ignore', '-q', str(rt.LOCAL / 'probe')], cwd=rt.ROOT)
    assert ignored.returncode == 0
    return dict(files=len(rt.INPUTS), changed=changed, local_ignored=True)


def seal(check_only=False):
    files = sorted(p for p in rt.HERE.rglob('*') if p.is_file() and not p.is_relative_to(rt.LOCAL)
        and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)
    listing = rt.HERE / 'SHA256SUMS'
    content = ''.join(rt.sha(p) + '  ' + str(p.relative_to(rt.HERE)) + '\n' for p in files)
    if not check_only: listing.write_text(content)
    assert listing.read_text() == content
    for line in listing.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        assert rt.sha(rt.HERE / name) == digest
    rt.dump('checksum_verification.json', dict(status='ALL_OK', nonlocal_files=len(files),
        includes_all_nonlocal_files_except_self=True))
    print('SHA256SUMS: ALL OK', len(files), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--isolation', action='store_true')
    parser.add_argument('--seal', action='store_true')
    parser.add_argument('--checksums-only', action='store_true')
    args = parser.parse_args()
    if args.checksums_only:
        seal(True)
        return
    result = dict(status='PASS', numeric=numeric_checks(), acceptance=acceptance_checks())
    isolation_path = rt.LOCAL / 'isolation_verification.json'
    context = {name: rt.sha(rt.HERE / name) for name in ('fit.py', 'simulator.py', 'local/dense.npz', 'local/calibration/P0.json')}
    if args.isolation:
        rt.dump('isolation_verification.json', dict(context=context, result=isolation_check()))
    if isolation_path.exists():
        saved = rt.read(isolation_path)
        if saved['context'] == context: result['isolation'] = saved['result']
    result['inputs'] = input_check()
    rt.dump('verification.json', result)
    print(json.dumps(rt.plain(result), ensure_ascii=False, indent=2), flush=True)
    if args.seal: seal()


if __name__ == '__main__': main()
