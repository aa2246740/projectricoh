"""Recompute scene regressions from saved record bytes, without fitting."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
from entry_codec import predict, record_checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit', required=True)
    ap.add_argument('--tag', required=True)
    args = ap.parse_args()
    path = rt.HERE/args.fit
    assert path.resolve().is_relative_to(rt.LOCAL/'fits')
    doc = rt.read(path)
    unit, index = doc['unit'], doc['index']
    ui = ('a12-50', 'a12-28', 'mount-a12').index(unit)
    record = path.with_suffix('.record552').read_bytes()
    assert record_checks(record)['sha256'] == doc['record']['sha256']
    folder = rt.LOCAL/'scene_reviews'/args.tag
    folder.mkdir(parents=True, exist_ok=False)
    target = rt.LOCAL/'targets'/unit
    meta = rt.read(target/f'{index:02d}.json')
    current = bytes.fromhex(meta['template_hex'])
    photos = rt.read(rt.LOCAL/'inputs'/unit/'photos.json')
    rows, scene_rows, diagnostics = [], [], []
    for group in ('train', 'synthetic', 'photo_iso200', 'photo_other_iso'):
        data = rt.arrays(target/f'{index:02d}_{group}.npz')
        if not len(data['x']):
            continue
        before = predict(current, data['x'], ui)
        after = predict(record, data['x'], ui)
        assert np.array_equal(before, data['current'])
        ordinary = bytearray(record)
        ordinary[0] = 1
        independent = np.rint(rt.camera_model(ui).predict(bytes(ordinary), data['x']))
        assert np.array_equal(after, independent)
        saved = rt.arrays(path.parent/(path.stem+'_'+group+'.npz'))['prediction']
        assert np.array_equal(after, saved)
        lab = rt.lab_from_codes(data['want'])
        e0 = rt.delta_e00(rt.lab_from_codes(before), lab)
        e1 = rt.delta_e00(rt.lab_from_codes(after), lab)
        np.savez_compressed(folder/(group+'.npz'), current_error=e0, candidate_error=e1,
                            target_lightness=lab[:, 0], photo_id=data['photo_id'])
        def summarize(use):
            return dict(points=int(use.sum()), current_de00=rt.stats(e0[use]), candidate_de00=rt.stats(e1[use]),
                        current_weighted_square=float(np.average(e0[use]**2, weights=data['sw'][use])),
                        candidate_weighted_square=float(np.average(e1[use]**2, weights=data['sw'][use])),
                        points_improved=int((e1[use]<e0[use]-1e-10).sum()),
                        points_worsened=int((e1[use]>e0[use]+1e-10).sum()))
        diagnostics.append(dict(group=group, **summarize(np.ones(len(e0), bool))))
        if not group.startswith('photo_'):
            continue
        ids = data['photo_id'].astype(int)
        names = np.array([photos[i]['scene_group'] for i in ids])
        for scene in sorted(set(names)):
            use = names == scene
            bins = []
            for lo, hi in ((0, 10), (10, 25), (25, 50), (50, 75), (75, 101)):
                selected = use & (lab[:, 0]>=lo) & (lab[:, 0]<hi)
                if selected.any():
                    bins.append(dict(target_L_min=lo, target_L_max=hi, **summarize(selected)))
            scene_rows.append(dict(group=group, scene=scene, **summarize(use), lightness_bins=bins))
        for i in sorted(set(ids)):
            info = photos[i]
            rows.append(dict(group=group, photo_id=int(i), scene=info['scene_group'],
                             source=info, **summarize(ids==i)))
    result = dict(label='电脑预测', created_utc=rt.utc(), fit_receipt=args.fit,
                  record_sha256=doc['record']['sha256'], target_sha256=rt.sha(target/f'{index:02d}.json'),
                  integer_predictions_recomputed=True, saved_predictions_equal=True,
                  ordinary_Standard_predictions_equal=True, parameter_reselection=False,
                  groups=diagnostics, scenes=scene_rows, photos=rows)
    rt.dump(folder/'review.json', result)
    public = {k:v for k,v in result.items() if k!='photos'}
    public['photographs'] = [dict(group=r['group'], photo_id=r['photo_id'], scene=r['scene'],
        points=r['points'], current_de00=r['current_de00'], candidate_de00=r['candidate_de00']) for r in rows]
    rt.dump('mount03_scene_review.json', public)
    for row in scene_rows:
        if row['group']=='photo_iso200':
            print(row['scene'], row['points'], 'median', row['current_de00']['median'],
                  row['candidate_de00']['median'], 'p95', row['current_de00']['p95'], row['candidate_de00']['p95'])


if __name__ == '__main__':
    main()
