"""Pool observed holdouts and report source, hue and lightness limitations."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, dump
from score import runtime, strata
import csv
import json
import numpy as np


def main():
    guard()
    r = runtime()
    old = read(ROOT / 'research/color_fit_v2/gr_dense_t1/baseline_metrics.json')
    baseline = {}
    for group in ('gr3', 'gr4_hdf'):
        for slot in ('01', '02'):
            dd = r.P.dense(group, slot)
            tr = r.P.Transfer(group, 'positive' if slot == '01' else 'negative', r.P.G, r.generator)
            target, valid = r.P.observed_targets(group, slot, dd, tr)
            base = r.FS.lab_from_codes(dd['rgb04'])
            row = {}
            for iso in (200, 1600):
                D = r.P.data_of(slot, iso)
                pred = r.P.prediction(D, D.current, dd['input_x'])
                row[str(iso)] = r.score(target[valid], pred[valid], base[valid])
                expected = old[group + '_' + slot]['models'][str(iso)]['observed_dense']
                assert row[str(iso)]['n'] == expected['n']
                for metric in ('median', 'p90', 'similarity'):
                    assert abs(row[str(iso)][metric] - expected[metric]) < 1e-10
            baseline[group + '_' + slot] = row
    dump(HERE / 'baseline_recomputed.json', baseline)
    arrays, counts, rows = [], {}, []
    for f in read(LOCAL / 'inventory.json'):
        q = read(HERE / ('scores_' + f['id'] + '.json'))
        with np.load(LOCAL / ('scores_' + f['id'] + '.npz'), allow_pickle=False) as z:
            d = dict(z)
        use = d['valid']
        counts[f['id']] = {k: q[k] for k in ('source_points', 'feature_thinned_points',
            'physically_eligible_points', 'supported_points', 'excluded_unsupported_standard')}
        source_hue = np.degrees(np.arctan2(d['source_scene_lab'][:, 2], d['source_scene_lab'][:, 1])) % 360
        source_C = np.hypot(d['source_scene_lab'][:, 1], d['source_scene_lab'][:, 2])
        counts[f['id']]['scene_D50_150_270_scored_chromatic'] = int((use & (source_C >= 8) & (source_hue >= 150) & (source_hue < 270)).sum())
        counts[f['id']]['scene_D50_180_240_scored_chromatic'] = int((use & (source_C >= 8) & (source_hue >= 180) & (source_hue < 240)).sum())
        if f['group'] == 'A':
            arrays.append({k: v[use] for k, v in d.items() if k in ('target', 'base', 'pred200', 'pred1600')})
        for iso in (200, 1600):
            reference = baseline[q['reference_group'] + '_' + q['slot']][str(iso)]
            sc = q['models'][str(iso)]['score']
            summary = dict(id=f['id'], group=f['group'], slot=q['slot'], iso=iso,
                n=sc['n'], median=sc['median'], p90=sc['p90'], lt2=sc['fractions']['lt2'],
                stock04_median=sc['stock04']['median'], similarity=sc['similarity'],
                reference_similarity=reference['similarity'], delta_percentage_points=100 * (sc['similarity'] - reference['similarity']))
            rows.append(summary)
            ss = q['models'][str(iso)]['strata']
            worst = sorted([x for x in ss if x['kind'] in ('hue', 'neutral')], key=lambda x: -x['squared_error_share'])[:3]
            print(json.dumps(dict(**summary, worst=worst), ensure_ascii=False))
    combined = {k: np.concatenate([d[k] for d in arrays]) for k in arrays[0]}
    pooled = dict(group='A', frames=['SC0134', 'SC0434'], pooling='Concatenate supported feature-thinned observations; recompute medians and ratio, no averaging percentages', models={})
    for iso in (200, 1600):
        t, p, b = combined['target'], combined['pred' + str(iso)], combined['base']
        pooled['models'][str(iso)] = dict(score=r.score(t, p, b), residual=r.decomposition(t, p), strata=strata(r, t, p, b))
        sc = pooled['models'][str(iso)]['score']
        ref = baseline['gr4_hdf_01'][str(iso)]
        rows.append(dict(id='A_pooled', group='A', slot='01', iso=iso, n=sc['n'],
            median=sc['median'], p90=sc['p90'], lt2=sc['fractions']['lt2'],
            stock04_median=sc['stock04']['median'], similarity=sc['similarity'],
            reference_similarity=ref['similarity'], delta_percentage_points=100*(sc['similarity']-ref['similarity'])))
    dump(HERE / 'scores_A_pooled.json', pooled)
    dump(HERE / 'support_counts.json', counts)
    with (HERE / 'scores.csv').open('w') as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    dump(HERE / 'scores_summary.json', rows)
    print(json.dumps(dict(pooled={iso: q['score'] for iso, q in pooled['models'].items()}, counts=counts)))


if __name__ == '__main__':
    main()
