"""Count complete row pools for proposed combinations without serializing any DAT."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

assert sys.flags.isolated
HERE = Path(__file__).resolve().parent
LOCAL = HERE/'local'
spec = importlib.util.spec_from_file_location('film_r2_row_pool_count', HERE/'export.py')
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
UNITS = E.UNITS
pspec=importlib.util.spec_from_file_location('film_r2_shared_promotion',HERE/'promote_probe.py')
P=importlib.util.module_from_spec(pspec);pspec.loader.exec_module(P)


def copied(value):
    slots, looks = value
    return ({u: dict(rows) for u, rows in slots.items()},
            {u: dict(rows) for u, rows in looks.items()})


def candidate_bytes(position):
    p = Path(position['record_file'])
    b = p.read_bytes()
    assert E.sha(b) == position['sha256'] and len(b) == 552
    return b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    summary = E.read(LOCAL/'summary.json')
    ds=importlib.util.spec_from_file_location('film_r2_capacity_rows',E.ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/camdata/datcodec.py')
    D=importlib.util.module_from_spec(ds);sys.modules[ds.name]=D;ds.loader.exec_module(D)
    if args.require_complete:
        assert summary['complete']
    scenarios = [];individual_Looks=[]
    films = {x['name']: x for x in summary['films']}
    illustration = ('Portra 160', 'Pro 400H', 'Gold 200', 'Ektar 100',
                    'Provia 100F', 'Velvia 50', 'Verita 200D')
    for profile in ('release', 'test'):
        baseline = E.layout(profile)
        baseline_size = E.count(*baseline)['row_pool_bytes']

        def record(name, layout, **extra):
            value = E.count(*layout)
            value.update(profile=profile, scenario=name,
                         net_bytes_vs_frozen_g157=E.count(*layout)['row_pool_bytes']-baseline_size,
                         includes_engine_code_or_BSS=False,
                         installability_asserted=False, **extra)
            scenarios.append(value)

        record('frozen_g157_18_Looks', baseline)
        locked = copied(baseline)
        locked[1].clear()
        locked[1].update({u: {} for u in UNITS})
        for item in summary['locked_Looks']:
            for unit in UNITS:
                locked[1][unit][item['name']] = candidate_bytes(item['units'][unit]['Look'])
        empty=(locked[0],{u:{} for u in UNITS})
        for item in summary['locked_Looks']:
            one=copied(empty)
            for unit in UNITS:one[1][unit][item['name']]=candidate_bytes(item['units'][unit]['Look'])
            counted=E.count(*one)
            individual_Looks.append(dict(profile=profile,name=item['name'],
                three_unit_net_bytes_over_same_builtins=counted['row_pool_bytes']-E.count(*empty)['row_pool_bytes'],
                physical_descriptors=counted['physical_Look_descriptors']))
        record('recommended_locked_Looks_original_builtins', locked,
               logical_locked_names=[x['name'] for x in summary['locked_Looks']],
               complete_recommendation=summary['complete'])
        if all(name in films and films[name]['complete'] for name in illustration):
            # Only byte0 is adjusted in memory for counting. Identity/metadata are
            # deliberately not serialized or claimed to have been rebuilt.
            for name, slots, chosen in (
                ('five_L1_current_anchor_compatible', (1, 2, 6, 7, 8), illustration[:5]),
                ('seven_L1_shows_current_anchor_conflict', (1, 2, 3, 5, 6, 7, 8), illustration),
            ):
                value = copied(locked)
                for slot, film_name in zip(slots, chosen):
                    for unit in UNITS:
                        b = bytearray(candidate_bytes(films[film_name]['units'][unit]['full']))
                        b[0] = slot
                        value[0][unit][slot] = bytes(b)
                record(name, value, assigned_slots=list(slots), assigned_films=list(chosen),
                       count_only_byte0_rebinding=True,
                       all_recipe_quality_gates_pass=all(films[n]['all_units_robust'] for n in chosen),
                       current_engine_anchor_contract_applies=True,
                       seven_slot_decoupling_cost_not_estimated=True)
                if len(slots)==7:
                    promoted=copied(value)
                    eligible=all(b[114]>=128 for rows in promoted[1].values() for b in rows.values())
                    if eligible:
                        for ui,unit in enumerate(UNITS):
                            for label,b in promoted[1][unit].items():
                                promoted[1][unit][label]=P.promote(b,1<<ui,D)
                        result=E.count(*promoted);assert result['layout_flags_pass']
                        record('seven_L1_shared_Looks_flags7_aliased_RGB',promoted,
                               assigned_slots=list(slots),assigned_films=list(chosen),
                               Look_shared_curve_semantics_preserved=True,
                               additional_Look_curve_parameters=0,additional_Look_curve_rows=0,
                               count_only_byte0_rebinding=True,
                               requires_fixed_base_application_metadata_and_Studio_atomic_transcoding=True,
                               no_engine_L1_expansion_needed_for_this_encoding=True)
    doc = dict(schema='gxr-film-row-pool-combinations/1', complete_input=summary['complete'],
               scenarios=scenarios, individual_Looks=individual_Looks,expanded_full_record_bytes=552,
               locked_Look_capacity_target=18, GXFX_physical_descriptor_limit=48,
               worst_case_18_independent_three_unit_Looks_descriptors=54,
               base_pool_limits=[144, 240, 48, 48], extra_pool_limit_per_kind=127,
               shared_row_sizes=[62, 33, 96, 56],
               combination_note='These exact pool counts use frozen g157 layouts and candidate bytes. '
               'They exclude engine/BSS and are not DAT or camera acceptance. '
               'The seven-slot count deliberately retains current anchors to expose flags conflicts; '
               'a future independent anchor layout must be recounted after implementation.',
               illustration_is_not_a_user_vote=True)
    path = LOCAL/'capacity.json'
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n')
    for item in scenarios:
        print(item['profile'], item['scenario'], item['row_pool_bytes'],
              'net', item['net_bytes_vs_frozen_g157'],
              'descriptors', item['physical_Look_descriptors'],
              'flags', item['layout_flags_pass'], 'limits',
              item['pool_limits_pass'] and item['descriptor_limit_pass'])


if __name__ == '__main__':
    main()
