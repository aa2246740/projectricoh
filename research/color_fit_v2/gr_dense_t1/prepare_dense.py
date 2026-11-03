"""Freeze source-aware nested folds before fitting any new recipe."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import argparse
import numpy as np


def path(group, slot, kind, index=None):
    suffix = kind if index is None else f'{kind}_{index:02d}'
    return r.LOCAL / 'datasets' / f'{group}_{slot}_{suffix}.npz'


def prepare(group, slot, kind='full', index=None):
    dst = path(group, slot, kind, index)
    assert not dst.exists(), 'Fold already prepared; use its recorded input hash'
    data = r.data(slot)
    d = r.P.dense(group, slot)
    t = r.transfer(group, slot)
    eval_target, eval_valid = r.P.observed_targets(group, slot, d, t)
    anchor = np.ones(24, bool)
    train = (d['aux_weights'] > 0) & d['mode_supported'] & d['standard_supported']
    held = np.zeros(len(train), bool)
    rule = dict(group=group, slot=slot, kind=kind, index=index,
                heldout_targets_never_fit_target_functions=True,
                dense_weights_never_renormalized_after_holdout=True)
    if kind == 'image':
        assert group == 'gr4_hdf'
        if index == 0:
            held = train.copy()
            train[:] = False
            rule['training_sources'] = ['bastibe_24_anchors']
            rule['heldout'] = 'entire HDF style image'
        else:
            anchor[:] = False
            rule['training_sources'] = ['HDF_dense_empirical_intersection']
            rule['heldout'] = 'entire bastibe RAW and all its anchors'
            rule['baseline_has_seen_bastibe'] = True
    elif kind == 'hue':
        _, chroma, hue = r.FS.lch(r.FS.lab_from_codes(d['rgb04']))
        ah = r.FS.lch(r.FS.lab_from_codes(data.a['chart_rgb04']))[2]
        held = r.P.hdist(hue, index*60) & (chroma >= 8)
        train &= ~(r.P.hdist(hue, (index*60-5) % 360, 70) & (chroma >= 8))
        anchor &= ~(r.P.hdist(ah, (index*60-5) % 360, 70) & np.isin(np.arange(24), data.chrom))
        t, details = r.P.restricted_transfer(group, slot, t, d, kind, index)
        rule.update(details, interval=[index*60, (index+1)*60], buffer_deg=5)
    elif kind == 'loo':
        anchor[index] = False
        t, details = r.P.restricted_transfer(group, slot, t, d, kind, index)
        rule.update(details, heldout_label=data.meta['labels'][index])
        if group == 'gr3':
            f = r.P.feature(t.bridge.to_gr(d['input_x']))
            train &= np.linalg.norm((f-np.asarray(details['excluded_camera_colour_centre']))/r.P.SCALE, axis=1) > 2
    if kind in ('hue', 'loo'):
        target, ms, ss, conf, _ = t.target(data, d['input_x'], d['rgb04'])
        d['aux_target'] = target
        train &= ms & ss & (conf >= .9)
    dst.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst, x=d['input_x'], target=d['aux_target'], eval_target=eval_target,
                        eval_valid=eval_valid, train=train, held=held, anchor=anchor,
                        weight=d['aux_weights'], rgb04=d['rgb04'], source_xy=d['source_xy'])
    rule.update(anchor_training=int(anchor.sum()), dense_training=int(train.sum()),
                dense_weight=float(d['aux_weights'][train].sum()),
                heldout_evaluable=int((held & eval_valid).sum()), dataset_sha256=r.sha(dst))
    r.dump(dst.with_suffix('.json'), rule)
    print(group, slot, kind, index, 'train', int(train.sum()), 'weight', round(rule['dense_weight'], 4), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--group', choices=('gr3', 'gr4_hdf'), required=True)
    p.add_argument('--slot', choices=('01', '02'), required=True)
    p.add_argument('--kind', choices=('full', 'loo', 'hue', 'image'), default='full')
    p.add_argument('--start', type=int)
    p.add_argument('--end', type=int)
    a = p.parse_args()
    for i in ([None] if a.start is None else range(a.start, a.end or a.start+1)):
        prepare(a.group, a.slot, a.kind, i)
