"""Per-photo error summaries from record-replayed integer predictions."""
import runtime as rt
from runtime import np
from pathlib import Path


def rows(doc, group, values, prediction, photos):
    target_lab = rt.lab_from_codes(values['want'])
    errors = {
        'current':rt.delta_e00(rt.lab_from_codes(values['current']), target_lab),
        'candidate':rt.delta_e00(rt.lab_from_codes(prediction), target_lab),
        'base':rt.delta_e00(rt.lab_from_codes(values['base']), target_lab),
    }
    ids = values['photo_id'].astype(int)
    result = []
    for photo_id in sorted(set(ids)):
        selected = ids==photo_id
        photo = photos[photo_id]
        stats = {name:rt.stats(error[selected]) for name,error in errors.items()}
        denominator = stats['base']['median']
        current = None if denominator<.25 else 100*(1-stats['current']['median']/denominator)
        candidate = None if denominator<.25 else 100*(1-stats['candidate']['median']/denominator)
        result.append(dict(label='电脑预测', unit=doc['unit'], index=doc['index'], name=doc['name'],
            record_sha256=doc['record']['sha256'], group=group, photo_id=int(photo_id),
            filename=Path(photo['path']).name, raw_sha256=photo['sha256'], scene=photo['scene_group'],
            iso=photo['iso'], points=int(selected.sum()),
            current_percent=current, candidate_percent=candidate,
            gain_pp=None if current is None else candidate-current,
            current_median_de00=stats['current']['median'], candidate_median_de00=stats['candidate']['median'],
            current_p95_de00=stats['current']['p95'], candidate_p95_de00=stats['candidate']['p95'],
            current_max_de00=stats['current']['max'], candidate_max_de00=stats['candidate']['max'],
            median_regressed=stats['candidate']['median']>stats['current']['median']+1e-10,
            p95_regressed=stats['candidate']['p95']>stats['current']['p95']+1e-10,
            used_to_select_parameters=False))
    return result
