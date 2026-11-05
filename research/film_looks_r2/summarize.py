"""Reclassify saved evidence with one position rule; publish no private pixels or rows."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

assert sys.flags.isolated
HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
UNITS = ('a12-50', 'a12-28', 'mount-a12')
STYLE_ORDER = (6, 53, 17, 18, 23, 16, 50, 51, 52, 10, 15, 9, 0, 3, 1, 2)
REVISION = '2pp_median025_quant128_finite_effect_observed'
WIRE_NAMES = {'ARRI Classic709':'ARRI 709','Acros official':'Acros',
              'Leica Natural official':'LeicaNatural','Leica Pure official':'LeicaPure',
              'Leica Cine official':'LeicaCine','RED Film Bias':'RED F.Bias',
              'Leica Classic':'LeicaClassic','千禧回声 A':'QianXi A','千禧回声 B':'QianXi B'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, data):
    path = LOCAL / name
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def stats(values):
    values = [x for x in values if x is not None and math.isfinite(x)]
    return dict(n=len(values), median=statistics.median(values) if values else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def safe(gap, penalty):
    return gap is not None and math.isfinite(gap) and gap < 2 and penalty <= .25


def position(doc, film=False):
    quant = doc['quantization']
    nominal = safe(doc['full_minus_Look_pp'], doc['Look_extra_median_de00'])
    branches = sum(safe(q['full_minus_Look_pp'],
                        q['Look_extra_median_de00'] if film else q['Look_extra_de00'])
                   for q in quant)
    left = doc['routes'][doc['selected_Look_route']] if film else doc['Look']
    right = doc['routes'][doc['selected_route']] if film else doc['full']
    quality = left['quality']['passes'] and right['quality']['passes']
    complete = bool(doc['placement_classification_complete']) if film else True
    # Two solvers retaining stock04 do not establish that a style fits Look.
    # This is an evidence gate, never a new way to select fitting parameters.
    effect_observed = all(row['scores']['photo_iso200']['similarity_percent'] is not None and
                          row['scores']['photo_iso200']['similarity_percent'] > 0
                          for row in (left, right))
    result = dict(Look_safe=bool(complete and effect_observed and nominal and len(quant) == 128 and branches == 128 and quality),
                  classification_complete=complete, full_minus_Look_pp=doc['full_minus_Look_pp'],
                  Look_extra_median_de00=doc['Look_extra_median_de00'],
                  safe_branches=branches, branches=len(quant), quality=quality,
                  fit_effect_observed=effect_observed,
                  position_gap_within_budget=bool(nominal and len(quant)==128 and branches==128))
    for key, value in (('Look', left), ('full', right)):
        path = Path(value['record_file'])
        assert sha(path) == value['record_sha256']
        score = value['scores']['photo_iso200']
        result[key] = dict(record_file=str(path), sha256=value['record_sha256'],
                           similarity_percent=score['similarity_percent'], de00=score['de00'],
                           flags=path.read_bytes()[1], reference_exact=value['reference_exact_checked'],
                           all_starts_converged=value.get('all_solver_starts_converged',
                                                          value.get('all_starts_converged')))
    return result


def weighted_comparison(doc):
    routes = doc['routes']
    # Compare to the unweighted training winner among the two unweighted methods.
    name = min(('scene_rgb_matrix', 'scene_structure'),
               key=lambda r: (routes[r]['unweighted_integer_training_loss'], r))
    base, weighted = (routes[r]['scores']['photo_iso200'] for r in (name, 'scene_weighted'))
    colors = {}
    for key in ('skin', 'sky', 'foliage'):
        a, b = (x['color_regions'][key] for x in (base, weighted))
        colors[key] = dict(n=min(a['n'], b['n']), before=a['median'], after=b['median'],
                           delta_de00=None if a['median'] is None or b['median'] is None else b['median']-a['median'])
    eligible = [x for x in colors.values() if x['n'] >= 20]
    delta = None if base['similarity_percent'] is None or weighted['similarity_percent'] is None else weighted['similarity_percent']-base['similarity_percent']
    p95 = weighted['de00']['p95']-base['de00']['p95']
    acceptable = bool(eligible and delta is not None and delta >= -1 and p95 <= .25 and
                      sum(x['delta_de00'] for x in eligible) < -.05 and
                      all(x['delta_de00'] <= .25 for x in eligible))
    return dict(unweighted_route=name, similarity_change_pp=delta, p95_change_de00=p95,
                colors=colors, meets_color_and_overall_budget=acceptable,
                reference_exact=routes['scene_weighted']['reference_exact_checked'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    catalog = read(LOCAL/'catalog.json')
    films, styles = [], []
    counts = dict(film_profiles=0, style_profiles=0)
    raw = {}
    for film in catalog['films']:
        units = {}
        for unit in UNITS:
            path = LOCAL/'analysis'/f'{film["ordinal"]:02d}'/unit/'final.json'
            if not path.exists():
                continue
            doc = read(path)
            fresh=(doc.get('analysis_revision')=='r3_unweighted_primary_weighted_control' and
                   doc['selected_route'] in ('scene_rgb_matrix','scene_structure') and
                   all(sha(row['record_file'])==row['record_sha256'] for row in doc['routes'].values()))
            if not fresh:
                assert not args.require_complete,'Stale analysis after record encoding repair: '+str(path)
                continue
            result = position(doc, True)
            selected = doc['routes'][doc['selected_route']]
            result.update(quantization_passes=doc['quantization_passes'],
                          selected_route=doc['selected_route'],
                          training_improved=doc['training_improved_vs_stock04'],
                          photo_improved=doc['primary_photo_improved_vs_baseline'],
                          gray_shape=doc['tone'].get('gray_shape'),
                          weighted=weighted_comparison(doc), analysis_file=str(path))
            result['robust_model_candidate'] = bool(result['training_improved'] and result['photo_improved'] and
                                                     result['quantization_passes'] == 128 and selected['quality']['passes'])
            shape=result['gray_shape']
            result['gray_shape_warning']=bool(shape and shape['maximum_Lstar_drawdown'] is not None and
                shape['maximum_Lstar_drawdown']>shape['target_maximum_Lstar_drawdown']+.5)
            result['default_shortlist_eligible']=bool(result['robust_model_candidate'] and shape is not None and not result['gray_shape_warning'])
            units[unit] = result
            raw[film['ordinal'], unit] = doc
            counts['film_profiles'] += 1
        complete = len(units) == 3
        numerical = complete and all(x['Look_safe'] for x in units.values())
        policy = film['family'] not in ('bw', 'instant')
        films.append(dict(ordinal=film['ordinal'], id=film['id'], name=film['name'],
                          provider=film['provider'], family=film['family'], units=units, complete=complete,
                          numerical_Look_safe=bool(numerical), policy_full=policy,
                          placement='Look' if numerical and not policy else 'full',
                          all_units_robust=complete and all(x['robust_model_candidate'] for x in units.values()),
                          all_units_default_shortlist_eligible=complete and all(x['default_shortlist_eligible'] for x in units.values())))
    for index in STYLE_ORDER:
        units, name = {}, None
        for unit in UNITS:
            path = LOCAL/'style_analysis'/f'{index:02d}'/(unit+'.json')
            if not path.exists():
                continue
            doc = read(path)
            name = doc['name']
            units[unit] = position(doc)
            counts['style_profiles'] += 1
        if name is not None:
            complete = len(units) == 3
            styles.append(dict(index=index, name=name, units=units, complete=complete,
                               placement_evidence_sufficient=bool(complete and all(x['fit_effect_observed'] for x in units.values())),
                               numerical_Look_safe=bool(complete and all(x['Look_safe'] for x in units.values()))))
    if args.require_complete:
        assert counts == dict(film_profiles=60, style_profiles=48), counts
    locks = [dict(kind='style', key=s['index'], name=s['name'], units=s['units'])
             for s in styles if s['numerical_Look_safe']]
    # Black-and-white / instant references may use Look only when all units pass.
    for film in films:
        if film['numerical_Look_safe'] and not film['policy_full']:
            locks.append(dict(kind='film', key=film['ordinal'], name=film['name'], units=film['units']))
    assert len(locks) <= 18
    for item in locks:
        tag=WIRE_NAMES.get(item['name'],item['name'])
        raw_tag=tag.encode('ascii')
        assert 1<=len(raw_tag)<=12 and all(32<=c<=126 and c not in (42,92) for c in raw_tag)
        item['wire_name']=tag
    assert len({x['wire_name'] for x in locks})==len(locks)
    names = read(LOCAL/'g157_layouts/release/manifest.json')['records']
    existing = list(dict.fromkeys(x['name'] for x in names if x['kind'] == 'look'))
    changes = []
    for name in existing:
        target_name = 'Acros official' if name == 'Acros' else name
        target = next((x for x in locks if x['name'] == target_name), None)
        film = next((x for x in films if x['name'] == name), None)
        style = next((x for x in styles if x['name'] == target_name), None)
        complete = target is not None or bool((film or style or {}).get('complete'))
        action = 'replace_Alchemy_with_official_and_lock' if target and name == 'Acros' else 'lock' if target else 'move_to_full_vote' if complete else 'pending'
        reason='policy_full' if film and film['policy_full'] else 'position_gap_or_quantization' if complete and not target else 'all_units_Look_safe' if target else 'incomplete'
        if not target and complete and film and not film['all_units_default_shortlist_eligible']:
            action,reason='full_research_hold','full_quantization_or_gray_admission_failed'
        elif not target and complete and style:
            action,reason='full_candidate_pending_release_gates','full_position_only_release_gates_pending'
        changes.append(dict(name=name, action=action,
                            reason=reason))
    route_summary = []
    for label, route in (('Look training winner', 'LOOK'), ('Full black box', 'scene_rgb_matrix'),
                         ('Full structure surrogate', 'scene_structure'), ('Full weighted', 'scene_weighted'),
                         ('Full unweighted training winner', 'FULL')):
        by_unit = {}
        for unit in UNITS:
            values = []
            for film in catalog['films']:
                doc = raw.get((film['ordinal'], unit))
                if doc is None:
                    continue
                chosen = doc['selected_Look_route'] if route == 'LOOK' else doc['selected_route'] if route == 'FULL' else route
                values.append(doc['routes'][chosen]['scores']['photo_iso200']['similarity_percent'])
            by_unit[unit] = stats(values)
        route_summary.append(dict(label=label, route=route, units=by_unit))
    save('summary.json', dict(revision=REVISION, counts=counts, complete=counts == dict(film_profiles=60, style_profiles=48),
                              films=films, styles=styles, route_summary=route_summary,
                              paired_full_minus_Look_pp={u:stats(f['units'][u]['full_minus_Look_pp'] for f in films if u in f['units']) for u in UNITS},
                              locked_Looks=locks, existing_g157_actions=changes,
                              thresholds=dict(pp_strictly_below=2, median_de00_at_most=.25, quantization=128,
                                              both_positions_must_improve_photo_median_vs_stock04=True,
                                              undefined_similarity_is_not_a_positive_Look_safe_classification=True),
                              extra_weighted_exact_confirmation_uses_photo_color_and_overall_budget=True,
                              photo_usage='Photo holdout values do not enter solver residuals or within-fit parameter selection. Training includes synthetic inputs and preassigned training-photo inputs. Primary photo validation can trigger additional weighted exact confirmation and admits or rejects recommendations; recommendation scores are not a new blind test.',
                              no_new_candidate_camera_exposures=True))
    print('SUMMARY', counts, 'locked candidates', len(locks))


if __name__ == '__main__':
    main()
