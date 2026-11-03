"""Freeze scene splits and reuse screened dense targets; never decode a new corpus."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import numpy as np
import csv

b = r.b


def put(ident, x, target, base, valid, role, generation, weight=None, **extra):
    values = dict(x=x, target=target, base=base, valid=np.asarray(valid, bool), **extra)
    if weight is not None:
        values['weight'] = weight
    r.save(b.LOCAL / 'datasets' / (ident + '.npz'), **values)
    return dict(id=ident, role=role, generation=generation, total=len(x), n=int(np.sum(valid)))


def main():
    assert not (b.LOCAL / 'protocol.json').exists(), 'Frozen split already exists'
    protocol = dict(task='gr4-positive-r1', levers='Y row, 24 symmetric rotate/scale sectors; fixed common tone curve',
        training_scenes=['hdf_positive', 'gr4b_positive'],
        selection='Two leave-one-scene-out fits per ridge; maximize worst held-scene similarity change; ties choose stronger ridge',
        ridge_multipliers=[0.5, 2.0, 8.0], max_nfev=70, integer_passes=0,
        blind_holdouts=['SC0134', 'SC0434', 'R0003037'],
        gr3_caveat='bastibe RAW trained historical round5; no independent default-positive GR III scene exists',
        anchor='Frozen 118 convention, common-white sensor bridge, 0 EV; no score-selected exposure or WB',
        promotion=dict(each_gr4_scene_median_regression_max_de00=0.05,
                       each_gr4_scene_p90_regression_max_de00=0.10,
                       each_gr3_reference_median_regression_max_de00=0.05,
                       each_gr3_reference_p90_regression_max_de00=0.10,
                       six_greys_max_de00_increase=0.05, neutral_axis_max_de00_change=0.05,
                       min_hue_derivative=0.1, max_dlog_chroma_per_degree=0.05,
                       min_relative_chroma_scale=0.25, require_convergence=True),
        noise='Paired JPEG embedded/standalone sensitivity and scene-level deltas; patch bootstrap is conditional only',
        real_gxr='Current-table pixels observed; new-table outputs simulated. No new-table camera measurement available')
    r.dump(b.LOCAL / 'protocol.json', protocol)
    r.dump(b.HERE / 'protocol.json', protocol)
    records = []
    for group, ident, generation, role in (
        ('gr4_hdf', 'hdf_positive', 'GR IV', 'train'),
        ('gr4_b', 'gr4b_positive', 'GR IV', 'train'),
        ('gr3', 'bastibe_whole', 'GR III', 'fidelity_reference')):
        d = r.P.dense(group, '01')
        x = d['input_x']
        base = r.FS.lab_from_codes(d['rgb04'])
        if group != 'gr4_b':
            target, valid = r.P.observed_targets(group, '01', d, r.transfer(group))
            weight = d['aux_weights']
        else:
            # Use the same HDF Standard convention as the independent web holdouts.
            # This body has no own Standard; the borrowed Standard is labelled.
            obs = r.P.samples(['gr4b_positive'])
            lookup = {(int(x), int(y)): i for i, (x, y) in enumerate(obs['xy'])}
            ix = np.array([lookup[(int(x), int(y))] for x, y in d['source_xy']])
            standard, _, _, support, _ = r.transfer().labs(x)
            styled = r.CM.rgb_lab(obs['jpeg'][ix] / 255)
            target = r.P.apply_relative(base, standard, styled)
            valid = support & d['mode_supported']
            weight = d['aux_weights'] / 0.2
        weight = np.where(valid, weight, 0.)
        records.append(put(ident, x, target, base, valid, role, generation, weight=weight,
                           source_xy=d['source_xy']))
    for ident in ('SC0134', 'SC0434'):
        a = r.arrays(b.ROOT / 'research/gr_webpairs/local' / ('scores_' + ident + '.npz'))
        target = r.P.apply_relative(a['base'], a['standard'], a['style_observed'])
        assert np.max(abs(target-a['target'])) < 1e-9
        assert np.max(abs(r.predict(r.data().current, a['x'])-a['pred200'])) < 1e-9
        records.append(put(ident, a['x'], target, a['base'], a['valid'], 'blind_holdout', 'GR IV',
            eligible=a['eligible'], alternate_target=a['embedded_target'], source_xy=a['xy']))
    for kind in ('roi', 'whole_flat'):
        a = r.arrays(b.ROOT / 'research/gr_hdfchart/local' / ('R0003037_' + kind + '_scores.npz'))
        assert np.max(abs(r.predict(r.data().current, a['x'])-a['pred200'])) < 1e-9
        ident = 'R0003037_' + kind
        records.append(put(ident, a['x'], a['target'], a['base'], a['valid'], 'discounted_holdout', 'GR IV',
            eligible=a['eligible'], alternate_target=a['fw_target'], ids=a['ids']))
        records.append(put(ident + '_proxy', a['x'], a['fw_target'], a['base'], a['eligible'],
            'discounted_proxy_diagnostic', 'GR IV', ids=a['ids']))
    D = r.data()
    records.append(put('bastibe_18', D.a['chart_x']*D.a['exposure'], D.a['chart_target'],
        r.FS.lab_from_codes(D.a['chart_rgb04']), np.isin(np.arange(24), D.chrom),
        'fidelity_reference', 'GR III'))
    r.dump(b.LOCAL / 'datasets.json', records)
    coverage = []
    for rec in records:
        a = r.dataset(rec['id']); L, C, h = r.FS.lch(a['base']); valid = a['valid']
        masks = [('neutral', -1, C < 8)]
        masks += [('hue', lo, (C >= 8) & (h >= lo) & (h < lo+30)) for lo in range(0, 360, 30)]
        masks += [('L', lo, (L >= lo) & ((L < lo+20) if lo < 80 else True)) for lo in range(0, 100, 20)]
        masks += [('hue_L', lo*100+ll, (C >= 8) & (h >= lo) & (h < lo+30) & (L >= ll) &
                   ((L < ll+20) if ll < 80 else True)) for lo in range(0, 360, 30) for ll in range(0, 100, 20)]
        for kind, start, m in masks:
            coverage.append(dict(id=rec['id'], role=rec['role'], generation=rec['generation'],
                coordinates='GXR04 Lab D65', kind=kind, start=start, available=int(m.sum()), scored=int((m&valid).sum())))
    with (b.HERE / 'coverage.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage[0])); writer.writeheader(); writer.writerows(coverage)
    r.dump(b.HERE / 'dataset_summary.json', records)
    print([(d['id'], d['role'], d['n']) for d in records])


if __name__ == '__main__':
    main()
