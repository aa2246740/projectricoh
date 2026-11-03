#!/usr/bin/env python3
"""R7 optimizer and folds, new independent paired GR IV target, entry 02 only."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
from target import DenseTarget

R7 = rt.ROOT / 'research/refit_50mm_r7'
FOLDS = [f'page{i}' for i in range(1, 7)] + [f'hue{i}' for i in range(3)] + ['full']


def modules():
    rt.calibration_modules()
    f = rt.module('refit', R7 / 'refit.py')
    d = rt.module('dense_r7_direct', R7 / 'direct_fit.py')
    return f, d


def prepare():
    f, _ = modules()
    m = rt.model()
    rows, good, arrays = f.data(m)
    q = arrays['02']['measured']
    lookup = {(r['page'], r['patch_id']): r for r in rows['04']}
    base_rows = [lookup[r['page'], r['patch_id']] for r in q]
    base_rgb = np.array([r['jpeg_rgb'] for r in base_rows])
    base_raw = np.array([np.array(r['raw_rgb']) * r['meta']['white_balance']['gains'] for r in base_rows])
    bx, bad_inverse = m.inverse04(base_rgb, base_raw)
    own_raw = np.array([r['raw'] for r in q])
    scene_x = bx * own_raw / np.maximum(base_raw, 1e-9)
    # Same 04 conditioning and own-frame RAW exposure correction as the frozen scoring pipeline.
    scene_base = m.fs.lab_from_codes(m.predict('04', scene_x))
    target, supported, distance = DenseTarget().target(scene_x, scene_base)
    supported &= ~bad_inverse
    known04 = {(r['page'], r['patch_id']) for r in arrays['02']['rows']}
    usable = {(r['frame'], r['patch_id']) for r in rows['02'] if r['usable']}
    fit_usable = np.array([(r['frame'], r['patch_id']) in usable and (r['page'], r['patch_id']) in known04 for r in q])
    old = np.array([r['target'] for r in q])
    folder = rt.LOCAL / 'fit'
    folder.mkdir(exist_ok=True)
    np.savez_compressed(folder / 'data.npz', raw=own_raw, scene_x=scene_x, base_rgb=base_rgb,
        observed_rgb=np.array([r['observed_rgb'] for r in q]), new_target=target, old_target=old,
        supported=supported, nearest_feature_distance=distance, fit_usable=fit_usable,
        pages=np.array([r['page'] for r in q]), hue_group=np.array([r['hue_group'] for r in q]),
        original_r7_baseline_de00=np.array([r['baseline_de00'] for r in q]))
    rt.dump('fit/records.json', [{k: r[k] for k in ('frame', 'patch_id', 'page', 'key', 'hue_group')} for r in q])
    rt.dump('fit/protocol.json', dict(schema='gr4-dense-refit/1', n_original=len(q),
        n_supported=int(supported.sum()), n_train_usable=int((supported & fit_usable).sum()),
        excluded=[dict(frame=r['frame'], patch_id=r['patch_id'], page=r['page'],
            inverse_failed=bool(bad_inverse[i]), nearest_distance=float(distance[i]))
            for i, r in enumerate(q) if not supported[i]],
        folds=FOLDS, optimizer='unchanged refit_50mm_r7 direct_fit.Problem, guarded',
        optimizer_centre='same original 44a0ff9e measured table as r7; current v6 02 is the comparison; export keeps the Positive candidate unchanged',
        budget='shared RGB curve outputs +/-8, Y independent coefficients +/-128, symmetric sectors +/-48; r7 regularization and dense guard',
        target_coordinates='own RAW / paired 04 RAW times paired 04 inverse, then new paired GR IV interpolation',
        denominator='literal paired 04 to the same target as recipe, separately for old and new targets',
        prior='existing fold-specific r7 04 calibration and original-table residual prior, held page/hue excluded',
        inherited_history='r7/current table and response kernel already have calibration history; this validates the incremental fit under those frozen priors',
        selection='fit only the new target; no hyperparameter selection by holdout scores',
        warm_start='all folds start from v6 entry02, represented by r7 guarded/full/02 theta; exact saved-table equivalence independently checked',
        camera_acceptance=False, firmware_ready=False))
    rt.s.finish(rt.LOCAL / 'fit/input_hashes.json')
    print('scoring original / new-supported / training-usable:', len(q), int(supported.sum()),
          int((supported & fit_usable).sum()), flush=True)


def run_fold(fold, max_nfev=80):
    f, d = modules()
    destination = rt.LOCAL / f'fit/folds/{fold}.json'
    if destination.exists():
        existing = rt.read(destination)
        if existing['candidate']['solver_success']:
            print('retained converged', fold, flush=True)
            return
    m = rt.model()
    rows, _, _ = f.data(m)
    with np.load(rt.LOCAL / 'fit/data.npz', allow_pickle=False) as z:
        data = dict(z)
    records = rt.read('fit/records.json')
    supported = data['supported']
    held = (data['pages'] == int(fold[4:])) if fold.startswith('page') else (
        data['hue_group'] == int(fold[3:])) if fold.startswith('hue') else np.zeros(len(records), bool)
    cal_path = R7 / f'local/folds/{fold}/calibration.json'
    prior_path = R7 / f'local/folds/{fold}/02_prior.json'
    cal, prior = rt.read(cal_path), rt.read(prior_path)
    assert cal['solver_success'] and prior['holdout_excluded']
    row_groups = {(r['page'], r['patch_id']): r['hue_group'] for r in rows['02'] if r['usable']}
    if fold.startswith('page'):
        assert all(page != int(fold[4:]) for page, pid in prior['training_keys'])
    elif fold.startswith('hue'):
        assert all(row_groups[page, pid] != int(fold[3:]) for page, pid in prior['training_keys'])
    x = rt.calibrate.apply_calibration(data['raw'], cal)
    native = m.predict('02', x, unclipped=True)
    bias, unsupported_prior = rt.calibrate.prior_bias(prior, x, '02')
    train = ~held & data['fit_usable'] & supported
    assert train.sum() >= 80
    bias[train] = data['observed_rgb'][train] - native[train]
    # The target function has no GXR JPEG recipe pixels. Unsupported rows get
    # harmless finite placeholders and zero training/score membership.
    target = data['new_target'].copy()
    target[~supported] = 0.
    problem = d.Problem(m, '02', x, target, bias, train, curves=True, variant='guarded')
    warm_path = R7 / 'local/direct/guarded/full/02.json'
    warm = rt.read(warm_path)['candidate']
    problem.initial = np.array(warm['theta'])
    if destination.exists():
        previous = rt.read(destination)
        # Preserve a nonconverged attempt before continuing from its exact state.
        rt.dump(f'fit/solver_attempts/{fold}-{previous["candidate"]["solver_nfev"]}.json', previous)
        problem.initial = np.array(previous['candidate']['theta'])
    candidate = problem.fit(max_nfev=max_nfev)
    assert all(candidate['checks'].values()), candidate['checks']
    candidate_rgb = d.predict(m, '02', candidate, x, unclipped=True)
    current = rt.read(R7 / 'local/direct/guarded/full/02.json')['candidate']
    current_rgb = d.predict(m, '02', current, x, unclipped=True)
    predicted = dict(current=np.clip(current_rgb + bias, 0, 255), candidate=np.clip(candidate_rgb + bias, 0, 255),
        candidate_projection=np.clip(data['observed_rgb'] + candidate_rgb - native, 0, 255),
        current_projection=np.clip(data['observed_rgb'] + current_rgb - native, 0, 255))
    base_lab = m.fs.lab_from_codes(data['base_rgb'])
    points = []
    for i in np.flatnonzero(held & supported):
        p = dict(records[i], fold=fold)
        for name, tt in [('old', data['old_target']), ('new', data['new_target'])]:
            p[name] = dict(baseline=float(m.fs.delta_e00(base_lab[i], tt[i])),
                **{key: float(m.fs.delta_e00(m.fs.lab_from_codes(rgb[i]), tt[i])) for key, rgb in predicted.items()})
        points.append(p)
    train_keys = [(r['frame'], r['patch_id']) for r, use in zip(records, train) if use]
    holdout_keys = [(r['frame'], r['patch_id']) for r, use in zip(records, held & supported) if use]
    assert set(train_keys).isdisjoint(holdout_keys)
    result = dict(fold=fold, candidate=candidate, n_train=int(train.sum()), n_holdout=int((held & supported).sum()),
        n_prior=len(prior['input_x']), unsupported_prior=unsupported_prior,
        train_keys=train_keys, holdout_keys=holdout_keys, points=points,
        calibration_sha256=rt.sha(cal_path), prior_sha256=rt.sha(prior_path),
        prior_holdout_exclusion_verified=True, current_table_prediction_is_model=True,
        candidate_prediction_is_model=True, camera_acceptance=False,
        scores={name: {key: f.score([p[name][key] for p in points], [p[name]['baseline'] for p in points])
                      for key in predicted} for name in ('old', 'new')})
    rt.dump(destination, result)
    rt.s.finish(rt.LOCAL / f'fit/folds/{fold}.inputs.json')
    print(fold, 'success', candidate['solver_success'], 'nfev', candidate['solver_nfev'],
        'new similarity', result['scores']['new']['candidate']['similarity_median'],
        'old similarity', result['scores']['old']['candidate']['similarity_median'], flush=True)


def summarize():
    f, _ = modules()
    result = dict(metric='1 - median(recipe to target DeltaE00) / median(paired04 to same target DeltaE00)',
        camera_acceptance=False, primary='fold model plus training-only residual interpolation',
        secondary='old observed JPEG plus new-minus-original response, conditional projection', schemes={})
    for scheme, folds in [('page', FOLDS[:6]), ('hue', FOLDS[6:9])]:
        docs = [rt.read(f'fit/folds/{fold}.json') for fold in folds]
        assert all(doc['candidate']['solver_success'] for doc in docs)
        points = sum([doc['points'] for doc in docs], [])
        keys = [(p['frame'], p['patch_id']) for p in points]
        assert len(keys) == len(set(keys)) == rt.read('fit/protocol.json')['n_supported']
        result['schemes'][scheme] = dict(n=len(points), targets={name: {key: f.score(
            [p[name][key] for p in points], [p[name]['baseline'] for p in points])
            for key in ('current', 'candidate', 'current_projection', 'candidate_projection')}
            for name in ('old', 'new')}, folds=[dict(fold=d['fold'], n_train=d['n_train'], n_holdout=d['n_holdout'],
                scores=d['scores'], sector_guard_alpha=d['candidate']['sector_guard']['alpha']) for d in docs])
        rt.dump(f'fit/oof_{scheme}.json', points)
    rt.dump('fit/summary.json', result)
    for scheme, q in result['schemes'].items():
        print(scheme, {name: {key: round(scores['similarity_median']*100, 2) for key, scores in val.items()}
                       for name, val in q['targets'].items()}, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--fold', choices=FOLDS)
    ap.add_argument('--max-nfev', type=int, default=80)
    ap.add_argument('--summarize', action='store_true')
    args = ap.parse_args()
    if args.prepare:
        prepare()
    if args.fold:
        run_fold(args.fold, args.max_nfev)
    if args.summarize:
        summarize()
