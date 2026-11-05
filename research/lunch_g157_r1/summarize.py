"""Aggregate held-out accuracy and style scores, and locate the final repeated scene."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
from collections import Counter


def loaded(pid):
    with C.np.load(C.LOCAL / 'frames' / pid / 'samples.npz', allow_pickle=False) as z:
        return dict(z)


def concatenate(parts):
    return C.np.concatenate(parts) if parts else C.np.empty(0)


def hue_masks(xyz):
    np = C.np
    lab = C.lab(np.clip(C.xyz_to_encoded(xyz, 'srgb'), 0, 1)*255, 'D65')
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    h = np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360
    colorful = chroma >= 8
    masks = dict(neutral=~colorful,
        red=colorful & ((h < 45) | (h >= 345)), yellow=colorful & (h >= 45) & (h < 100),
        green=colorful & (h >= 100) & (h < 190), cyan=colorful & (h >= 190) & (h < 250),
        blue=colorful & (h >= 250) & (h < 300), magenta=colorful & (h >= 300) & (h < 345))
    masks.update(dark=lab[:, 0] < 35, middle=(lab[:, 0] >= 35) & (lab[:, 0] < 75), bright=lab[:, 0] >= 75)
    return masks


def aggregate(rows, bank):
    np = C.np
    groups = {}
    overall = dict(D50=[], D65=[], photo_medians=[], regions={})
    for row in rows:
        v = loaded(row['id'])
        held = v['held']
        j = row['best_index']
        r = groups.setdefault(row['best'], dict(ids=[], accepted=0, uncertain=0, D50=[], D65=[],
             legacy50=[], photo_medians=[], regions={}, styles={'old': {}, 'r2': {}},
             style_regions={'old': {}, 'r2': {}}, similarity_photos=[]))
        r['ids'].append(row['id'])
        r['accepted'] += int(row['accepted'])
        r['uncertain'] += int(not row['accepted'])
        r['D50'].append(v['errors50'][j, held])
        r['D65'].append(v['errors65'][j, held])
        oldmask = v['legacy_mask'] & (v['cells'].sum(1)%2 == 1)
        r['legacy50'].append(v['errors50'][j, oldmask])
        r['photo_medians'].append(row['prediction_D50']['median'])
        overall['D50'].append(v['errors50'][j, held])
        overall['D65'].append(v['errors65'][j, held])
        overall['photo_medians'].append(row['prediction_D50']['median'])
        residual = C.lab(v['observed'][held]) - C.lab(v['predictions'][j, held])
        masks = hue_masks(v['xyz'][held])
        for name, mask in masks.items():
            if not mask.any():
                continue
            for container in (r['regions'], overall['regions']):
                region = container.setdefault(name, dict(errors=[], residual=[]))
                region['errors'].append(v['errors50'][j, held][mask])
                region['residual'].append(residual[mask])
        tp = C.LOCAL / 'frames' / row['id'] / 'targets.npz'
        if tp.exists():
            with np.load(tp, allow_pickle=False) as z:
                target = dict(z)
            doc = C.read(tp.with_suffix('.json'))['scores'][0]
            r['similarity_photos'].append(dict(id=row['id'], original=doc['g157_original_target'], scene=doc['film_r2_target']))
            for mode in ('old', 'r2'):
                for part in ('actual_target', 'predicted_target', 'baseline_target'):
                    key = f'best_{mode}_{part}'
                    if key in target:
                        r['styles'][mode].setdefault(part, []).append(target[key])
                wantkey = f'best_{mode}_want'
                if wantkey in target:
                    supported = target['best_supported']
                    delta = C.lab(v['observed'][held][supported], 'D65') - C.lab(target[wantkey][supported], 'D65')
                    for name, regionmask in masks.items():
                        use = regionmask[supported]
                        if not use.any():
                            continue
                        region = r['style_regions'][mode].setdefault(name, dict(actual=[], predicted=[], baseline=[], residual=[]))
                        for short, long in (('actual', 'actual_target'), ('predicted', 'predicted_target'), ('baseline', 'baseline_target')):
                            region[short].append(target[f'best_{mode}_{long}'][use])
                        region['residual'].append(delta[use])
    def region_summary(regions):
        return {key:dict(de00=C.stats(concatenate(v['errors'])),
                         actual_minus_predicted_Lab_median=np.median(concatenate(v['residual']), axis=0))
                for key, v in regions.items()}
    result = []
    for name, row in groups.items():
        styles = {}
        style_regions = {}
        for mode, value in row['styles'].items():
            if not value:
                styles[mode] = None
                continue
            st = {k:C.stats(concatenate(v)) for k, v in value.items()}
            denominator = st['baseline_target']['median']
            st.update(actual_similarity=None if denominator < .25 else 100*(1-st['actual_target']['median']/denominator),
                      model_similarity=None if denominator < .25 else 100*(1-st['predicted_target']['median']/denominator))
            styles[mode] = st
        for mode, regions in row['style_regions'].items():
            style_regions[mode] = {}
            for region_name, v in regions.items():
                actual, predicted, baseline = (C.stats(concatenate(v[key])) for key in ('actual', 'predicted', 'baseline'))
                den = baseline['median']
                style_regions[mode][region_name] = dict(actual=actual, predicted=predicted, baseline=baseline,
                    actual_similarity=None if den < .25 else 100*(1-actual['median']/den),
                    actual_minus_target_Lab_median=np.median(concatenate(v['residual']), axis=0))
        result.append(dict(name=name, photos=len(row['ids']), ids=row['ids'],
            accepted=row['accepted'], uncertain=row['uncertain'],
            prediction_D50=C.stats(concatenate(row['D50'])), prediction_D65=C.stats(concatenate(row['D65'])),
            legacy_mask_prediction_D50=C.stats(concatenate(row['legacy50'])),
            equal_photo_medians=C.stats(row['photo_medians']), regions=region_summary(row['regions']),
            style=styles, style_regions=style_regions, similarity_photos=row['similarity_photos']))
    return dict(photos=len(rows), accepted=sum(r['accepted'] for r in rows),
        overall_D50=C.stats(concatenate(overall['D50'])), overall_D65=C.stats(concatenate(overall['D65'])),
        equal_photo_medians=C.stats(overall['photo_medians']), regions=region_summary(overall['regions']), recipes=result)


def raw_structure(pid):
    np = C.np
    from scipy.ndimage import gaussian_filter
    with np.load(C.LOCAL / 'frames' / pid / 'preview-input.npz', allow_pickle=False) as z:
        raw = z['raw_codes']
    data = np.log2(np.maximum(raw[..., 1], 1))
    im = C.Image.fromarray(data.astype(np.float32)).resize((72, 48), C.Image.Resampling.BILINEAR)
    return gaussian_filter(np.asarray(im), .6)


def common_scene(rows):
    np = C.np
    structures = {r['id']:raw_structure(r['id']) for r in rows}
    def compare(reference, b):
        a = reference[8:-8, 8:-8]
        a = (a-a.mean()) / max(float(a.std()), 1e-12)
        best = (-2., None)
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                patch = b[8+dy:40+dy, 8+dx:64+dx]
                p = (patch-patch.mean()) / max(float(patch.std()), 1e-12)
                corr = float(np.mean(a*p))
                if corr > best[0]:
                    best = corr, [dx, dy]
        return best
    adjacent = []
    runs = [[rows[0]['id']]]
    for first, second in zip(rows, rows[1:]):
        corr, shift = compare(structures[first['id']], structures[second['id']])
        adjacent.append(dict(first=first['id'], second=second['id'], correlation=corr, shift_xy=shift))
        if corr >= .90:
            runs[-1].append(second['id'])
        else:
            runs.append([second['id']])
    repeated = max(runs, key=len)
    anchor_id = repeated[len(repeated)//2]
    matches = []
    for row in rows:
        best = compare(structures[anchor_id], structures[row['id']])
        matches.append(dict(id=row['id'], correlation=best[0], shift_thumbnail_xy=best[1],
                            raw_scene_match=best[0] >= .90))
    return dict(anchor=anchor_id, matches=matches, group_ids=repeated, adjacent=adjacent,
                contiguous_runs=runs,
                method='Longest contiguous run linked by RAW green log-luminance correlation, 72x48, central overlap, translation +/-6; threshold .90 fixed before matching; no recipe labels used',
                semantic_label_source='owner reports final billboard series; image contents never uploaded')


def main():
    C.admit('summary')
    C.numerical()
    C.sys.addaudithook(C.fence)
    bank = C.read(C.LOCAL / 'bank.json')['records']
    source = [r for r in C.read(C.LOCAL / 'inventory.json') if r['group'] != 'previous_day']
    rows = [C.read(C.LOCAL / 'frames' / r['id'] / 'result.json') for r in source]
    lunch = [r for r in rows if r['group'] == 'lunch']
    morning = [r for r in rows if r['group'] == 'morning']
    scene = common_scene(lunch)
    C.dump('scene-matching.json', scene)
    board_ids = set(scene['group_ids'])
    scopes = {'lunch': lunch, 'morning': morning, 'all_today': rows,
              'lunch_confident': [r for r in lunch if r['accepted']],
              'all_confident': [r for r in rows if r['accepted']],
              'final_scene': [r for r in lunch if r['id'] in board_ids]}
    summary = {name:aggregate(group, bank) for name, group in scopes.items()}
    outliers = sorted(rows, key=lambda r:r['prediction_D50']['median'], reverse=True)
    C.dump('summary.json', dict(scopes=summary, rows=rows, final_scene=scene,
         best_response_counts=dict(Counter(r['best'] for r in lunch)),
         ambiguous=[r['id'] for r in rows if not r['accepted']],
         largest_residuals=[dict(id=r['id'], name=r['best'],
             de00=r['prediction_D50'], gap=r['gap_de00'], accepted=r['accepted']) for r in outliers[:10]],
         weighting='pooled smooth held-out blocks; equal-photo median also reported',
         created_utc=C.utc()))
    C.decision('summary', '按空间留出汇总误差，并分别保留两种风格目标',
               '预测准确度和风格相似度回答不同问题；未知配方保留敏感性结果',
               'local/summary.json; local/scene-matching.json',
               f"lunch {summary['lunch']['accepted']}/44 accepted")
    print(C.json.dumps(dict(lunch=summary['lunch']['overall_D50'],
        identified=summary['lunch']['accepted'], counts=dict(Counter(r['best'] for r in lunch)),
        final_scene=scene['group_ids'], largest_residuals=[dict(id=r['id'], best=r['best'],
        median=r['prediction_D50']['median']) for r in outliers[:5]]), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
