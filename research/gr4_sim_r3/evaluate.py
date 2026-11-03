"""Evaluate frozen stage models once, with unchanged outer sample masks."""
from pathlib import Path
from dataclasses import replace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
import fit


def state_models():
    baseline = rt.read('research/gr4_analytic_target_r1/local/calibration/primary_pre_hard.json')['common']
    baseline.update(fit.metadata(), radial_kind='knots')
    states = {k: rt.read(rt.LOCAL / ('calibration/' + k + '.json')) for k in ('P0', 'P1', 'P2')}
    p0, p1, p2 = (states[k] for k in ('P0', 'P1', 'P2'))
    rows = [dict(name='r1_reference', common=baseline, options=sim.Options(), all_sources_radial=True),
        dict(name='P0_source_only', common=baseline, options=sim.Options()),
        dict(name='P0', common=p0['common'], options=sim.Options(**p0['options'])),
        dict(name='P1_front_fixed', common=p0['common'], options=sim.Options(front='integer')),
        dict(name='P1_nodes_fixed', common=p0['common'], options=sim.Options(gamma='u10')),
        dict(name='P1_increments_fixed', common=p0['common'], options=sim.Options(gamma='increments')),
        dict(name='P1_all_fixed', common=p0['common'], options=sim.Options(front='integer', gamma='increments')),
        dict(name='P1', common=p1['common'], options=sim.Options(**p1['options'])),
        dict(name='P2_native_fixed', common=p1['common'], options=sim.Options(**p2['options'])),
        dict(name='P2', common=p2['common'], options=sim.Options(**p2['options']))]
    return rows


def freeze():
    names = ['PROTOCOL.md', 'simulator.py', 'fit.py', 'prepare.py', 'new_samples.py', 'evaluate.py']
    lock = {n: rt.sha(rt.HERE / n) for n in names}
    lock.update({f'local/calibration/{k}.json': rt.sha(rt.LOCAL / f'calibration/{k}.json') for k in ('P0', 'P1', 'P2')})
    rt.dump('model_lock.json', dict(files=lock, selection_complete_before_outer_evaluation=True,
        candidate_condition='both final page4 film medians <= 1.0',
        evidence='对真实 GR IV 照片的验证'))
    return lock


def metric(predicted, observed):
    labp, labo = rt.lab(predicted), rt.lab(observed)
    dc = np.hypot(labp[:, 1], labp[:, 2]) - np.hypot(labo[:, 1], labo[:, 2])
    return dict(**rt.stats(rt.cm.delta_e00(labp, labo)),
        signed_dL_median=float(np.median(labp[:, 0] - labo[:, 0])),
        signed_dC_median=float(np.median(dc)))


def dense(model):
    a = rt.arrays(rt.LOCAL / 'dense.npz')
    rows, predictions = [], {}
    for mode in sim.MODES:
        predicted = fit.predict(a, model['common'], model['options'], mode)
        predictions[mode] = predicted
        for split, use0 in (('training_pages123', a['band'] < 4), ('held_page4', a['band'] == 4)):
            use = use0 & a[mode + '_valid'] & np.isin(a['role'], ['colour', 'tone', 'reference', 'natural'])
            rows.append(dict(model=model['name'], dataset='dense', split=split, mode=mode,
                evidence='对真实 GR IV 照片的验证', **metric(predicted[use], a[mode][use])))
            if split == 'held_page4':
                print(model['name'], split, mode, rows[-1]['median'], rows[-1]['p90'], rows[-1]['n'], flush=True)
    np.savez_compressed(rt.LOCAL / ('predictions_' + model['name'] + '.npz'), **predictions)
    return rows


def natural(model):
    rows = []
    for name, dataset in (('natural.npz', 'natural_standard'), ('natural_modes.npz', 'natural_modes')):
        a = rt.arrays('research/gr4_analytic_target_r1/local/' + name)
        output = {}
        for mode in sim.MODES:
            if 'mode' in a: use = (a['mode'] == mode) & a['defaults_verified']
            elif mode == 'standard': use = np.ones(len(a['raw_wb']), bool)
            else: continue
            if not use.any(): continue
            actual = a['observed'][use] if 'observed' in a else a['standard'][use]
            scene = a['scene'][use].copy()
            if model.get('all_sources_radial'):
                scene *= sim.radial_gain(a['radius'][use], model['common'])[:, None]
            predicted = sim.render_scene(scene, mode, model['common'], model['options'])
            output[mode] = predicted
            for frame in [*np.unique(a['frame'][use]), 'pooled']:
                mask = np.ones(use.sum(), bool) if frame == 'pooled' else a['frame'][use] == frame
                rows.append(dict(model=model['name'], dataset=dataset, split='whole_photo_holdout',
                    mode=mode, frame=str(frame), evidence='对真实 GR IV 照片的验证',
                    **metric(predicted[mask], actual[mask])))
        np.savez_compressed(rt.LOCAL / (dataset + '_' + model['name'] + '.npz'), **output)
    return rows


def new_samples(model):
    a = rt.arrays(rt.LOCAL / 'new_samples.npz')
    audits = rt.read(rt.LOCAL / 'new_samples_audit.json')
    rows, saved, actuals = [], [], []
    for row in audits:
        use = a['frame'] == row['frame']
        # No chart spatial gain applies to this source; BE is already in scene.
        scene = a['scene'][use].copy()
        if model.get('all_sources_radial'):
            scene *= sim.radial_gain(a['radius'][use], model['common'])[:, None]
        predicted = sim.render_scene(scene, 'standard', model['common'], model['options'], row['sliders'])
        observed = a['observed'][use]
        saved.append(predicted); actuals.append(observed)
        rows.append(dict(model=model['name'], dataset='new_embedded_preview', split='whole_photo_holdout',
            mode='standard_custom', frame=row['frame'], evidence='对真实 GR IV 照片的验证',
            separate_sooc_jpeg_equivalence_verified=False, **metric(predicted, observed)))
    rows.append(dict(model=model['name'], dataset='new_embedded_preview', split='whole_photo_holdout',
        mode='standard_custom', frame='pooled', evidence='对真实 GR IV 照片的验证',
        separate_sooc_jpeg_equivalence_verified=False, **metric(np.concatenate(saved), np.concatenate(actuals))))
    np.savez_compressed(rt.LOCAL / ('new_predictions_' + model['name'] + '.npz'), predicted=np.concatenate(saved))
    return rows


def main():
    lock = freeze()
    scores = []
    for model in state_models():
        scores += dense(model) + natural(model) + new_samples(model)
    checks = []
    for mode in ('positive', 'negative'):
        d = next(r for r in scores if r['model'] == 'P2' and r['dataset'] == 'dense' and r['split'] == 'held_page4' and r['mode'] == mode)
        natural_row = next(r for r in scores if r['model'] == 'P2' and r['dataset'] == 'natural_modes' and r['mode'] == mode and r['frame'] == 'pooled')
        checks.append(dict(mode=mode, dense_median=d['median'], dense_pass=d['median'] <= 1.,
            natural_median=natural_row['median'], natural_pass=natural_row['median'] <= 1.))
    accepted = all(c['dense_pass'] for c in checks)
    rt.dump('scores.json', scores)
    rt.dump('gate.json', dict(evidence='对真实 GR IV 照片的验证', checks=checks,
        accepted=accepted, threshold=1., candidate_generation_authorized=accepted,
        primary_model='P2', post_holdout_selection=False,
        extra_previews_are_standard_only=True, extra_previews_used_for_selection=False))
    assert all(rt.sha(rt.HERE / name) == digest for name, digest in lock.items())
    print('Final page holdout gate', accepted, checks, flush=True)


if __name__ == '__main__': main()
