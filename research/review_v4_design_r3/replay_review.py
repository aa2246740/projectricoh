#!/usr/bin/python3 -I -B
"""Read-only R4 record review. All created evidence stays in this directory."""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R4 = ROOT / 'research/body_v4_design/r4'
R3 = R4.parent / 'r3'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v4-r3')


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                       allow_nan=False) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def row(doc, scene):
    return next(r for r in doc['records'] if r['scene'] == scene)


def at(value, path):
    for key in path:
        value = value[key]
    return value


def replace(doc, path, value):
    at(doc, path[:-1])[path[-1]] = copy.deepcopy(value)


def shift_ticks(value, amount):
    names = {'start_tick', 'end_tick', 'tick', 'ready_tick', 'h09', 'h40', 'h41'}
    if type(value) is dict:
        for key, item in value.items():
            if key in names:
                value[key] = (item + amount) & 0xffffffff
            else:
                shift_ticks(item, amount)
    elif type(value) is list:
        for item in value:
            shift_ticks(item, amount)


def check_original_cli():
    original = R4 / 'cli_check.py'
    source = original.read_text()
    old = "SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r4')"
    new = 'SCRATCH=Path(' + repr(str(SCRATCH)) + ')'
    old_output = "(HERE/'cli-results.json').write_text"
    new_output = '(Path(' + repr(str(HERE / 'r4-cli-rerun.json')) + ')).write_text'
    assert source.count(old) == source.count(old_output) == 1
    adapted = source.replace(old, new).replace(old_output, new_output)
    compile(adapted, str(original), 'exec')
    save('cli-path-adapter.json', {
        'source': str(original.relative_to(ROOT)), 'source_sha256': digest(original),
        'replacements': [{'from': old, 'to': new}, {'from': old_output, 'to': new_output}],
        'logic_changed': False,
    })
    namespace = {'__file__': str(original), '__name__': 'review_cli_adapter'}
    exec(compile(adapted, str(original), 'exec'), namespace)
    namespace['main']()
    actual = json.loads((HERE / 'r4-cli-rerun.json').read_text())
    expected = json.loads((R4 / 'cli-results.json').read_text())
    assert actual == expected
    print('Saved 20 CLI cases match the fresh run exactly.')


def check_before():
    old = load_module('review_old_gate', R4 / 'before/diag_gate.py')
    fixtures = load_module('review_cases', R4 / 'record_cases.py')
    gold = json.loads((R4 / 'complete-records.json').read_text())
    previous = json.loads((ROOT / 'research/review_v4_design_r2/record-variants.json').read_text())
    results = []
    for case in previous['variants'][1:]:
        rebased = fixtures.apply_review_variant(copy.deepcopy(gold), case['name'])
        for group, doc in [('original', case['input']), ('complete_base', rebased)]:
            actual = old.classify(doc)
            results.append({'group': group, 'case': case['name'], 'result': actual,
                            'input_sha256': hashlib.sha256(encode(doc)).hexdigest()})
    assert len(results) == 12 and all(r['result']['record_stage'] == 'records_complete_for_offline_review' for r in results)
    save('before-rerun.json', {'cases': results, 'old_checker_sha256': digest(R4 / 'before/diag_gate.py')})
    print('The old checker accepts the six cases on both bases, 12 of 12.')


def differences(base, changed, path=()):
    if type(base) is dict and type(changed) is dict:
        result = []
        for key in sorted(base.keys() - changed.keys()):
            result.append({'op': 'delete', 'path': list(path + (key,))})
        for key in sorted(changed):
            if key not in base:
                result.append({'op': 'set', 'path': list(path + (key,)), 'value': changed[key]})
            else:
                result.extend(differences(base[key], changed[key], path + (key,)))
        return result
    if type(base) is list and type(changed) is list and len(base) == len(changed):
        result = []
        for i, (a, b) in enumerate(zip(base, changed)):
            result.extend(differences(a, b, path + (i,)))
        return result
    if type(base) is type(changed) and base == changed:
        return []
    return [{'op': 'set', 'path': list(path), 'value': changed}]


def paths(value, path=()):
    if type(value) is dict:
        for key, item in value.items():
            yield path + (key,), item
            yield from paths(item, path + (key,))
    elif type(value) is list:
        for index, item in enumerate(value):
            yield path + (index,), item
            yield from paths(item, path + (index,))


def independent_checks():
    gate = load_module('review_gate', R3 / 'diag_gate.py')
    fixtures = load_module('review_cases', R4 / 'record_cases.py')
    gold = json.loads((R4 / 'complete-records.json').read_text())
    raw_profile = json.loads((R4 / 'reference-profile.json').read_text())
    pin = (R4 / 'reference-profile.sha256').read_text().strip()
    reference = gate.load_profile(raw_profile, pin)
    cases = []

    def case(group, name, expected, change):
        doc = copy.deepcopy(gold)
        change(doc)
        actual = gate.classify(doc, reference)
        if actual['records_complete']:
            assert actual['record_stage'] == 'records_complete_for_offline_review'
            assert actual['reasons'] == {}
        else:
            assert actual['record_stage'] == 'undetermined'
            assert actual['verdict'] == '不完整、不通过'
            assert [actual[k] for k in ('capacity', 'h43', 'time')] == ['undetermined'] * 3
            assert [actual[k] for k in ('read_interval', 'control_interval', 'crc_interval')] == [None] * 3
        assert actual['er_ownership'] == 'not_established_by_diag'
        assert actual['h42_time'] == 'requires_final_v4_measurement'
        case_row = {'group': group, 'name': name, 'expected_complete': expected,
                    'actual_complete': actual['records_complete'],
                    'matches_expectation': actual['records_complete'] is expected,
                    'patches': differences(gold, doc),
                    'input_sha256': hashlib.sha256(encode(doc)).hexdigest(), 'result': actual}
        cases.append(case_row)
        return doc

    case('complete', 'unchanged_complete_base', True, lambda d: None)
    case('complete', 'distinct_k_interleaved_shots', True,
         lambda d: d.update(fixtures.interleaved_records(d)))
    for amount in (-0x100000000, -11000, -1010, -1000, -995, 1, 12345,
                   0x7fffffff, 0x80000000, 0xffff0000, 0xffffffff, 0x100000000):
        case('complete', 'all_ticks_shift_' + str(amount), True,
             lambda d, n=amount: shift_ticks(d, n))
    for scene in ('JPEG_L', 'RAW_L'):
        for index in range(11):
            def empty_category(doc, scene=scene, index=index):
                row(doc, scene)['categories'][index].update(count=0, addresses=[], stride_source='native_rule')
            case('complete', scene + '_empty_category_' + str(index), True, empty_category)
        case('complete', scene + '_category_array_reversed', True,
             lambda d, s=scene: row(d, s)['categories'].reverse())
        def capped(doc, scene=scene):
            for c in row(doc, scene)['categories']:
                c['count'] = 18
                c['addresses'] = [c['base'] + i*c['stride'] for i in range(18)]
        case('complete', scene + '_all_categories_capped_at_18', True, capped)
    for pair in (('GRID_OFF', 'GRID_ON'), ('INFO_OFF', 'INFO_ON')):
        def narrower(doc, pair=pair):
            for scene in pair:
                layer = row(doc, scene)['layers'][0]
                layer['width'] = 320
                for i, piece in enumerate(layer['pieces']):
                    piece.update(bytes=76800, offset=i*76800)
        case('complete', pair[0] + '_non_coordinate_layer_width_320', True, narrower)
        def reorder_both(doc, pair=pair):
            for scene in pair:
                row(doc, scene)['layers'].reverse()
        case('complete', pair[0] + '_both_layer_arrays_reversed', True, reorder_both)
    for dt in (4, 5, 7, 9):
        def quantized(doc, dt=dt):
            bw = row(doc, 'BW')
            for kind, offset in (('read', 10), ('control', 310), ('crc', 600)):
                for i, item in enumerate(bw[kind + '_samples']):
                    start = bw['start_tick'] + offset + i*dt
                    item.update(start_tick=start, end_tick=start+dt)
                bw[kind + '_ticks'] = [dt]*32
        case('complete', 'bw_valid_positive_ticks_' + str(dt), True, quantized)
    case('complete', 'complete_mem_with_different_observed_words', True,
         lambda d: row(d, 'PLAY')['mem_after'].update(values=list(range(16))))

    expected_counts = {'KEY': 4, 'GRID_OFF': 1, 'GRID_ON': 1, 'INFO_OFF': 1, 'INFO_ON': 1,
                       'JPEG_L': 1, 'RAW_L': 1, 'RAW_169': 1, 'BURST': 3, 'PLAY': 2, 'BW': 96}
    for scene, expected in expected_counts.items():
        for value in (1, 2, 3, 4, 5, 8, 20, 95, 96, 97, 0xffffffff):
            if value != expected:
                case('success_count_mismatch', scene + '_valid_' + str(value), False,
                     lambda d, s=scene, n=value: row(d, s).update(valid=n))
        case('reported_loss', scene + '_lost_one', False,
             lambda d, s=scene: row(d, s).update(lost=1))
        case('reported_loss', scene + '_overwritten_one', False,
             lambda d, s=scene: row(d, s).update(overwritten=1))

    for path, value in list(paths(gold)):
        if type(value) is dict and set(value) == {'boot', 'unit', 'unit_epoch', 'set', 'scene_id', 'config_version'}:
            other = copy.deepcopy(value)
            other['scene_id'] = other['scene_id'] % 11 + 1
            other['config_version'] += 1
            case('mixed_context', 'scene_and_configuration_' + json.dumps(path), False,
                 lambda d, p=path, x=other: replace(d, p, x))

    for left, right in (('GRID_OFF', 'GRID_ON'), ('INFO_OFF', 'INFO_ON')):
        for layer in range(5):
            case('spliced_osd', left + '_layer_from_' + right + '_' + str(layer), False,
                 lambda d, a=left, b=right, i=layer:
                 row(d, a)['layers'].__setitem__(i, copy.deepcopy(row(d, b)['layers'][i])))
            case('spliced_osd', left + '_piece_from_' + right + '_' + str(layer), False,
                 lambda d, a=left, b=right, i=layer:
                 row(d, a)['layers'][i]['pieces'].__setitem__(0, copy.deepcopy(row(d, b)['layers'][i]['pieces'][0])))
    for target in ('JPEG_L', 'RAW_L', 'RAW_169'):
        for source in ('JPEG_L', 'RAW_L', 'RAW_169'):
            if target != source:
                case('spliced_image', target + '_image_from_' + source, False,
                     lambda d, a=target, b=source: row(d, a).update(image=copy.deepcopy(row(d, b)['image'])))
    for index in range(3):
        case('spliced_shot', 'duplicate_shot_' + str(index), False,
             lambda d, i=index: row(d, 'BURST')['samples'].__setitem__(i, copy.deepcopy(row(d, 'BURST')['samples'][(i+1)%3])))
    for kind in ('read', 'control', 'crc'):
        for index in (0, 15, 31):
            case('spliced_bw', kind + '_duplicate_piece_' + str(index), False,
                 lambda d, k=kind, i=index: row(d, 'BW')[k+'_samples'].__setitem__(i,
                 copy.deepcopy(row(d, 'BW')[k+'_samples'][(i+1)%32])))
        case('spliced_bw', kind + '_old_frozen_set', False,
             lambda d, k=kind: [x['context'].update(set=10) for x in row(d, 'BW')[k+'_samples']])
    case('spliced_mem', 'before_is_copy_of_after', False,
         lambda d: row(d, 'PLAY').update(mem_before=copy.deepcopy(row(d, 'PLAY')['mem_after'])))

    for field in ('quality_id', 'aspect_id', 'display_width', 'display_height'):
        case('simultaneous_missing', 'all_osd_settings_missing_' + field, False,
             lambda d, f=field: [row(d, s)['other_settings'].pop(f)
                                for s in ('GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON')])
    for index in range(5):
        case('simultaneous_missing', 'both_grid_rectangles_missing_' + str(index), False,
             lambda d, i=index: [row(d, s)['layers'][i].pop('rectangles') for s in ('GRID_OFF', 'GRID_ON')])
    for scene in ('JPEG_L', 'RAW_L'):
        def omit_class(doc, scene=scene):
            r = row(doc, scene)
            r['category_ids'].remove(1)
            r['categories'] = [c for c in r['categories'] if c['id'] != 1]
            r['resources'] = [c for c in r['resources'] if c[0] != 1]
        case('simultaneous_missing', scene + '_all_three_category_lists_omit_one', False, omit_class)
    for key in ('body', 'build', 'abi', 'dat'):
        value = '9' * (32 if key == 'abi' else 64)
        case('reference_mismatch', 'wrong_identity_' + key, False,
             lambda d, k=key, v=value: d['identity'].update({k: v}))
    case('reference_mismatch', 'self_consistent_all_wrong_units', False,
         lambda d: [obj.update(unit='mount') for _, obj in paths(d)
                    if type(obj) is dict and 'unit' in obj])
    case('reference_mismatch', 'wrong_profile_digest', False,
         lambda d: d.update(profile_sha256='0'*64))
    case('reference_mismatch', 'synthetic_data_labelled_device_capture', False,
         lambda d: d.update(classification='device_capture'))
    for scene in ('JPEG_L', 'RAW_L', 'RAW_169'):
        for field in ('base', 'source', 'k'):
            case('invalid_image', scene + '_' + field + '_zero', False,
                 lambda d, s=scene, f=field: row(d, s)['image'].update({f: 0}))
        case('invalid_image', scene + '_short_range', False,
             lambda d, s=scene: row(d, s)['image'].update(range=[0x81000000, 0x81000020]))

    counts = {}
    for item in cases:
        c = counts.setdefault(item['group'], {'cases': 0, 'expected_complete': 0,
                                             'accepted': 0, 'matches': 0})
        c['cases'] += 1
        c['expected_complete'] += int(item['expected_complete'])
        c['accepted'] += int(item['actual_complete'])
        c['matches'] += int(item['matches_expectation'])
    wrong = [item['name'] for item in cases if not item['matches_expectation']]
    output = {'scope': 'independent_synthetic_record_contract_review_only',
              'checker_sha256': digest(R3/'diag_gate.py'), 'base_sha256': digest(R4/'complete-records.json'),
              'profile_sha256': pin, 'cases': cases, 'counts': counts,
              'unexpected_acceptance': [r['name'] for r in cases if not r['expected_complete'] and r['actual_complete']],
              'unexpected_rejection': [r['name'] for r in cases if r['expected_complete'] and not r['actual_complete']],
              'er_ownership_passes': 0, 'h42_time_passes': 0}
    save('independent-records.json', output)
    examples = []
    for scene in ('JPEG_L', 'RAW_L', 'RAW_169'):
        doc = copy.deepcopy(gold)
        row(doc, scene)['valid'] = 2
        examples.append({'name': scene + '_valid_2', 'input': doc, 'actual': gate.classify(doc, reference)})
    save('count-mismatch-examples.json', {'profile_sha256': pin, 'cases': examples})
    print(json.dumps({'total_cases': len(cases), 'counts': counts,
                      'unexpected_acceptance': len(output['unexpected_acceptance']),
                      'unexpected_rejection': len(output['unexpected_rejection'])}, ensure_ascii=False))
    return 1 if output['unexpected_acceptance'] or output['unexpected_rejection'] else 0


def extra_cli():
    import subprocess
    gate_path = R3 / 'diag_gate.py'
    pin = (R4 / 'reference-profile.sha256').read_text().strip()
    profile_path = R4 / 'reference-profile.json'
    gold = json.loads((R4 / 'complete-records.json').read_text())
    source = json.loads((HERE / 'independent-records.json').read_text())
    selected = [r for r in source['cases'] if (r['group'] == 'success_count_mismatch'
                and r['name'].endswith('_valid_2')) or r['name'] in
                ('unchanged_complete_base', 'distinct_k_interleaved_shots',
                 'JPEG_L_empty_category_1', 'GRID_OFF_both_layer_arrays_reversed')]
    results = []
    for item in selected:
        doc = copy.deepcopy(gold)
        for patch in item['patches']:
            if patch['op'] == 'delete':
                del at(doc, patch['path'][:-1])[patch['path'][-1]]
            else:
                replace(doc, patch['path'], patch['value'])
        assert hashlib.sha256(encode(doc)).hexdigest() == item['input_sha256']
        path = SCRATCH / (item['name'] + '.json')
        path.write_bytes(encode(doc))
        command = ['/usr/bin/python3', '-I', '-B', str(gate_path), str(path),
                   '--profile', str(profile_path), '--profile-sha256', pin]
        ran = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert ran.stderr == ''
        assert ran.returncode in (0, 2)
        actual = json.loads(ran.stdout)
        assert actual == item['result']
        results.append({'name': item['name'], 'expected_complete': item['expected_complete'],
                        'exitcode': ran.returncode, 'input_sha256': item['input_sha256'],
                        'actual': actual})
    save('independent-cli.json', {'cases': results, 'checker_sha256': digest(gate_path),
                                 'profile_sha256': pin, 'sequential': True})
    print(json.dumps({'cases': len(results), 'unexpected_acceptance':
                     sum(not r['expected_complete'] and r['exitcode'] == 0 for r in results)}))
    return 1 if any(not r['expected_complete'] and r['exitcode'] == 0 for r in results) else 0



def ordering_checks():
    gate = load_module('review_gate', R3 / 'diag_gate.py')
    gold = json.loads((R4 / 'complete-records.json').read_text())
    raw_profile = json.loads((R4 / 'reference-profile.json').read_text())
    reference = gate.load_profile(raw_profile, (R4 / 'reference-profile.sha256').read_text().strip())
    cases = []
    for scene in ('GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON'):
        reordered = copy.deepcopy(gold)
        row(reordered, scene)['layers'].reverse()
        actual = gate.classify(reordered, reference)
        assert actual['records_complete'] is False
        assert actual['reasons']['record'][0]['code'] == 'controlled_buffer_mismatch'
        normalized = copy.deepcopy(reordered)
        for r in normalized['records']:
            if 'layers' in r:
                r['layers'].sort(key=lambda layer: layer['index'])
        recovered = gate.classify(normalized, reference)
        assert recovered['records_complete'] is True
        cases.append({'name': scene + '_only_array_order_changed',
                      'all_indexed_measurements_preserved': True,
                      'patches': differences(gold, reordered),
                      'result': actual, 'normalized_result': recovered})
    save('ordering-observations.json', {'cases': cases, 'scope': 'exchange_order_contract_clarification',
                                      'checker_sha256': digest(R3/'diag_gate.py')})
    print('Four one-sided layer permutations are refused; sorting by index restores all four.')


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    assert SCRATCH.is_dir()
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['original-cli', 'before', 'independent', 'extra-cli', 'ordering'])
    args = parser.parse_args()
    return {'original-cli': check_original_cli, 'before': check_before, 'independent': independent_checks,
            'extra-cli': extra_cli, 'ordering': ordering_checks}[args.part]()


if __name__ == '__main__':
    raise SystemExit(main())
