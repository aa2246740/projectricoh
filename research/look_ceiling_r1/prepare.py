"""Recreate the published split and independently rescore all 27 integer baselines."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, ROOT, HERE, LOCAL, upstream as data

def main():
    scenes = data.scenes()
    model, dat, provenance = data.camera_model()
    camera = rt.Camera()
    x, sw = rt.samples(camera, 700, 151)
    ns = len(x)
    testx, _ = rt.samples(camera, 1400, 20261023)
    reference = next(a for a, meta in scenes if meta['unit'] == 'a12-50')
    xyz = camera.xyz(x, reference['neutral'], reference['matrix'])
    fit_scenes, hold_scenes = scenes[:3], scenes[3:]
    for a, meta in fit_scenes:
        valid = np.flatnonzero(a['valid'])
        take = valid[np.linspace(0, len(valid)-1, 140).astype(int)]
        x = np.vstack([x, a['codes'][take]])
        sw = np.r_[sw, np.ones(len(take))]
        xyz = np.vstack([xyz, a['xyz'][take]])
    groups = {'train': dict(x=x, xyz=xyz, sw=sw, unit='a12-50'),
              'synthetic': dict(x=testx, xyz=camera.xyz(testx, reference['neutral'], reference['matrix']),
                                sw=np.ones(len(testx)), unit='all')}
    photo_paths = {}
    for unit in ('a12-50', 'a12-28', 'mount-a12'):
        aa, zz, ids = [], [], []
        photo_paths[unit] = []
        for a, meta in hold_scenes:
            if meta['unit'] != unit:
                continue
            valid = np.flatnonzero(a['valid'])
            take = valid[np.linspace(0, len(valid)-1, min(2500, len(valid))).astype(int)]
            ids.extend([len(photo_paths[unit])] * len(take))
            photo_paths[unit].append(meta['path'])
            aa.append(a['codes'][take]); zz.append(a['xyz'][take])
        groups[unit] = dict(x=np.vstack(aa) if aa else np.empty((0, 3)),
            xyz=np.vstack(zz) if zz else np.empty((0, 3)),
            photo_id=np.array(ids), unit=unit)
    jobs = data.creator_jobs() + data.alchemy_jobs() + rt.fit_adapter.old_jobs(dat)
    old = rt.read(ROOT / 'artifacts/downloads/vlog-alchemy-eval-20261102/look_fits.json')
    fitted = rt.read(ROOT / 'artifacts/downloads/vlog-alchemy-eval-build-20261102/all_fitted_effects.json')
    existing = {j['name']: j['entry'] for j in jobs if j['family'] == 'existing'}
    for index, job in enumerate(jobs):
        name = job['name']
        target = rt.fit_adapter.target_of(job)
        old_row = next(r for r in old['fits'] if r['name'] == name)
        entry = existing[name] if name in existing else bytes.fromhex(next(
            r['entry_hex'] for r in fitted if r['source_sha256'] == rt.sha(job['path'])))
        arrays = {}
        scores = {}
        for key, group in groups.items():
            a = group['x']
            if not len(a):
                scores[key] = None
                continue
            ui = 2 if group['unit'] == 'mount-a12' else 1 if group['unit'] == 'a12-28' else 0
            base = model.predict(dat.entry_of(ui, 4), a, bw_chroma='zero')
            want = target.render(base, group['xyz'])
            pred = np.rint(model.predict(entry, a, bw_chroma='zero'))
            scores[key] = rt.score(base, pred, want)
            arrays[key + '_base'] = base
            arrays[key + '_target'] = want
            arrays[key + '_published'] = pred
            if key in ('a12-50', 'mount-a12'):
                previous = old_row['units'][key]['photo_holdout']
                assert abs(scores[key]['similarity_percent'] - previous['similarity_percent']) < 1e-10
                for field in ('median', 'p95', 'max'):
                    assert abs(scores[key]['de00'][field] - previous['de00'][field]) < 1e-10
        np.savez_compressed(LOCAL / f'target_{index:02d}.npz', **arrays)
        meta = dict(index=index, name=name, family=job['family'], source=str(job['path'].relative_to(ROOT)),
                    source_sha256=rt.sha(job['path']), input=job['input'], output=job['output'],
                    interpretation=job.get('interpretation', 'declared'), entry_hex=entry.hex(),
                    scores=scores, baseline_exact_reproduction=True)
        rt.dump(LOCAL / f'target_{index:02d}.json', meta)
        print(name, 'published MOUNT', scores['mount-a12']['similarity_percent'], flush=True)
    for key, group in groups.items():
        np.savez_compressed(LOCAL / ('samples_' + key + '.npz'),
            **{k: v for k, v in group.items() if isinstance(v, np.ndarray)})
    protocol=dict(label='电脑预测', targets=27, train_n=len(x), synthetic_train_n=ns,
        synthetic_holdout_n=len(testx), train_photos=[m['path'] for _, m in fit_scenes],
        holdout_photos=photo_paths, scene_inventory=[m for _, m in scenes], provenance=provenance,
        unit_scope={'a12-50': 'ISO200 标定模型，其他ISO为迁移', 'a12-28': '50mm模型迁移；无照片留出',
                    'mount-a12': '50mm模型迁移；未逐单元标定'},
        similarity='100 * (1 - median(DE00(candidate,target))/median(DE00(stock04,target)))',
        integer_parameters=True, final_output_rounding='numpy.rint to u8 code domain',
        internal_hardware_accumulator_rounding='unknown; not bit-exact ISP emulation',
        baseline_reproduction='27 targets, all reported photo median/p95/max and similarities exact')
    rt.dump(LOCAL/'protocol_private.json',protocol)
    public={**protocol,'scene_inventory':[{k:v for k,v in row.items() if k not in ('matrix','neutral','as_shot_neutral')}
                                       for row in protocol['scene_inventory']]}
    rt.dump('protocol.json',public)
    rt.finish('prepare')

if __name__ == '__main__':
    main()
