#!/usr/bin/python3 -I -B
"""离线复审。所有测试材料为主机合成记录，不代表相机采集。"""
import argparse
import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'research/body_v4_design'
R5 = BASE / 'r5'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v4-r4')
sys.path.insert(0, str(BASE / 'r3'))
import diag_gate as gate


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


def read(path):
    return gate.read_json(path)


def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def incomplete(result):
    assert result['records_complete'] is False
    assert result['record_stage'] == 'undetermined'
    assert result['verdict'] == '不完整、不通过'
    assert all(result[k] == 'undetermined' for k in ('capacity', 'h43', 'time'))
    assert all(result[k] is None for k in ('read_interval', 'control_interval', 'crc_interval'))
    assert result['er_ownership'] == 'not_established_by_diag'
    assert result['h42_time'] == 'requires_final_v4_measurement'


def evaluate(doc, profile, capture):
    try:
        profile_obj = gate.load_profile(profile, sha(profile))
        capture_obj = gate.load_capture(capture, sha(capture))
        return gate.validate_text(encoded(doc).decode(), profile_obj, capture_obj)
    except gate.InvalidRecord as error:
        return gate.incomplete(error.path, error.code)


def independent():
    index = read(R5 / 'positive-index.json')
    base = read(R5 / 'positive/00-record.json')
    profile = read(R5 / 'positive/00-profile.json')
    original = read(R5 / 'positive/00-capture.json')
    rows = []
    seen = set()

    def run(name, group, doc, expected=False, capture=None, reference=None, keep_digest=False):
        cap = copy.deepcopy(original if capture is None else capture)
        ref = profile if reference is None else reference
        if not keep_digest:
            cap['record_sha256'] = sha(doc)
        fingerprint = (sha(doc), sha(cap), sha(ref))
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        result = evaluate(doc, ref, cap)
        if expected:
            assert result['records_complete'] is True, (name, result)
            assert result['er_ownership'] == 'not_established_by_diag'
        else:
            incomplete(result)
            if not keep_digest:
                assert result['reasons']['record'][0]['code'] != 'frozen_record_changed'
        row = dict(name=name, group=group, input_sha256=sha(doc),
                   capture_sha256=sha(cap), profile_sha256=sha(ref),
                   expected_complete=expected, result=result)
        rows.append(row)
        if len(rows) <= 4 or name in ('count_JPEG_L_2', 'count_RAW_L_2', 'count_RAW_169_2',
                                    'slot_count_addresses_5_0', 'mixed_entries_5_image',
                                    'layout_consistent_summary', 'raw_bw_reads_value'):
            d = TMP / name
            d.mkdir(exist_ok=True)
            for kind, obj in (('record', doc), ('profile', ref), ('capture', cap)):
                (d / (kind + '.json')).write_bytes(encoded(obj))

    for item in index:
        stem = item['stem']
        doc = read(R5 / 'positive' / (stem + '-record.json'))
        ref = read(R5 / 'positive' / (stem + '-profile.json'))
        cap = read(R5 / 'positive' / (stem + '-capture.json'))
        assert sha(doc) == item['record_sha256'] and sha(ref) == item['profile_sha256']
        assert sha(cap) == item['capture_sha256']
        run('delivered_' + stem, 'delivered_positive', doc, True, cap, ref)
    for ri, record in enumerate(base['records']):
        for value in (2, 3, 7, 18, 95, 96, 97, 0xffffffff, 0, -1, True, 1.0):
            if type(value) is type(record['valid']) and value == record['valid']:
                continue
            doc = copy.deepcopy(base)
            doc['records'][ri]['valid'] = value
            run('count_' + record['scene'] + '_' + str(value), 'counts', doc)
        for field in ('lost', 'overwritten'):
            doc = copy.deepcopy(base)
            doc['records'][ri][field] = 1
            run(record['scene'] + '_' + field, 'completion_conflict', doc)
    for left, right in itertools.combinations(range(11), 2):
        doc = copy.deepcopy(base)
        for ri in (left, right):
            doc['records'][ri]['valid'] += 7
        run(f'paired_counts_{left}_{right}', 'paired_counts', doc)
    for ri in (5, 6):
        for ci, category in enumerate(base['records'][ri]['categories']):
            doc = copy.deepcopy(base)
            c = doc['records'][ri]['categories'][ci]
            if c['count'] == 18:
                c['addresses'].pop()
                c['count'] -= 1
            else:
                c['addresses'].append(c['base'] + c['count'] * c['stride'])
                c['count'] += 1
            run(f'slot_count_addresses_{ri}_{ci}', 'source_matrix_count', doc)
            for field in ('base', 'stride', 'stride_raw', 'count_address', 'stride_address', 'matrix_address'):
                doc = copy.deepcopy(base)
                doc['records'][ri]['categories'][ci][field] += 4
                run(f'slot_{ri}_{ci}_{field}', 'source_matrix_fields', doc)
    for n, old in enumerate(base['records']):
        paths = [('config_version',), ('boot',), ('unit_epoch',), ('set',), ('scene_id',)]
        if 'image' in old:
            paths += [('image', 'context', k) for k in ('boot', 'unit_epoch', 'set', 'scene_id', 'config_version')]
        if 'layers' in old:
            paths += [('layers', i, 'context', 'boot') for i in range(5)]
            paths += [('layers', i, 'pieces', 0, 'context', 'set') for i in range(5)]
        for path in paths:
            doc = copy.deepcopy(base)
            obj = doc['records'][n]
            for key in path[:-1]:
                obj = obj[key]
            obj[path[-1]] += 1
            run('context_' + str(n) + '_' + '_'.join(map(str, path)), 'mixed_context', doc)
    fields = ['snapshots', 'layers', 'image', 'samples', 'mem_before', 'mem_after',
              'read_samples', 'control_samples', 'crc_samples']
    for ri, record in enumerate(base['records']):
        for field in fields:
            if field not in record:
                continue
            doc = copy.deepcopy(base)
            def change(value):
                if isinstance(value, dict):
                    for k, v in value.items():
                        if k in ('boot', 'set', 'config_version'):
                            value[k] = v + 17
                        else:
                            change(v)
                elif isinstance(value, list):
                    for v in value:
                        change(v)
            change(doc['records'][ri][field])
            run(f'mixed_entries_{ri}_{field}', 'mixed_entries', doc)
    for field in ('file_bytes', 'bss_bytes', 'fixed_overhead', 'session_bytes', 'request', 'bss_begin', 'bss_end'):
        for amount in (-4, 4, 512):
            doc = copy.deepcopy(base)
            doc['allocation'][field] += amount
            run(f'layout_{field}_{amount}', 'layout_repack', doc)
    doc = copy.deepcopy(base)
    a = doc['allocation']
    a['file_bytes'] += 4
    a['request'] += 4
    a['bss_begin'] += 4
    a['bss_end'] += 4
    run('layout_consistent_summary', 'layout_repack', doc)
    for field in ('first_sequence', 'last_sequence'):
        doc = copy.deepcopy(base)
        doc[field] += 1
        run(field, 'sequences', doc)
    for ri, record in enumerate(base['records']):
        for field in ('snapshots', 'layers', 'samples', 'read_samples', 'control_samples', 'crc_samples'):
            if field not in record:
                continue
            for op in ('short', 'copy', 'reverse'):
                doc = copy.deepcopy(base)
                arr = doc['records'][ri][field]
                if op == 'short':
                    arr.pop()
                elif op == 'copy':
                    arr[-1] = copy.deepcopy(arr[0])
                else:
                    arr.reverse()
                expected = field == 'layers' and op == 'reverse'
                run(f'array_{ri}_{field}_{op}', 'array_positive' if expected else 'arrays', doc, expected)
    for kind in ('osd_reads', 'bw_reads', 'slot_scans'):
        for op in ('short', 'copy', 'index', 'value'):
            cap = copy.deepcopy(original)
            arr = cap['observations'][kind]
            if op == 'short':
                arr.pop()
            elif op == 'copy':
                arr[-1] = copy.deepcopy(arr[0])
            elif op == 'index':
                if kind == 'slot_scans':
                    arr[0]['rows'][0]['index'] = 1
                else:
                    arr[0]['sequence'] += 1
            elif kind == 'slot_scans':
                arr[0]['rows'][0]['count_raw'] += 1
            else:
                old_segment = arr[0]['segments'][0]
                size = len(bytes.fromhex(old_segment['pattern'])) * old_segment['repeats']
                arr[0]['segments'] = [dict(pattern='01000000', repeats=1), dict(pattern='00', repeats=size-4)]
            run('raw_' + kind + '_' + op, 'repacked_source', base, capture=cap)
    for ri in (5, 6):
        for ci in range(11):
            cap = copy.deepcopy(original)
            scan = cap['observations']['slot_scans'][ri - 5]['rows'][ci]
            if scan['count_raw'] > 0:
                scan['matrix_words'][scan['count_raw'] - 1] = 0
            else:
                scan['matrix_words'][1] = scan['base_raw']
            run(f'raw_matrix_{ri}_{ci}', 'repacked_source', base, capture=cap)
    for i in range(24):
        doc = copy.deepcopy(base)
        for record in doc['records']:
            def shift(value):
                if isinstance(value, dict):
                    for k, v in value.items():
                        if k in ('start_tick', 'end_tick', 'ready_tick', 'tick', 'h09', 'h40', 'h41'):
                            value[k] = (v + (0xfffff000 + i * 137)) & 0xffffffff
                        else:
                            shift(v)
                elif isinstance(value, list):
                    for v in value:
                        shift(v)
            shift(record)
        run(f'tick_translation_{i}', 'independent_positive', doc, True)
    for field in ('file_segments',):
        cap = copy.deepcopy(original)
        cap['observations'][field] = [dict(pattern='0000', repeats=10240)]
        run('equivalent_file_encoding', 'independent_positive', base, True, cap)
    cap = copy.deepcopy(original)
    spans = cap['observations']['bss_spans']
    left, right = spans[0]
    cap['observations']['bss_spans'] = [[left, left + 4096], [left + 4096, right]]
    run('equivalent_bss_spans', 'independent_positive', base, True, cap)
    counts = {}
    for row in rows:
        key = row['group']
        counts[key] = counts.get(key, 0) + 1
    result = dict(scope='主机合成记录；逐例重封摘要，保留底层来源', counts=counts,
                  accepted=sum(r['expected_complete'] for r in rows),
                  rejected=sum(not r['expected_complete'] for r in rows), cases=rows)
    write('independent-results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, ensure_ascii=False))


def coupled():
    mod = load('review_coupled_source', R5 / 'coupled_check.py')
    prior = read(R5 / 'coupled-results.json')['cases']
    rows = []
    for item in read(R5 / 'positive-index.json'):
        stem = item['stem']
        doc = read(R5 / 'positive' / (stem + '-record.json'))
        profile = read(R5 / 'positive' / (stem + '-profile.json'))
        cap = read(R5 / 'positive' / (stem + '-capture.json'))
        for name, changed in mod.variants(doc):
            current = copy.deepcopy(cap)
            current['record_sha256'] = sha(changed)
            actual = evaluate(changed, profile, current)
            incomplete(actual)
            assert actual['reasons']['record'][0]['code'] != 'frozen_record_changed'
            old = prior[len(rows)]
            assert (old['base'], old['name'], old['input_sha256'], old['capture_sha256']) == (stem, name, sha(changed), sha(current))
            rows.append(dict(base=stem, name=name, input_sha256=sha(changed), result=actual))
    assert len(rows) == 4158
    write('coupled-rerun.json', dict(cases=rows, rejected=len(rows), all_match_delivered_inputs=True))
    print(json.dumps(dict(coupled_rejected=len(rows))))


def history(start, stop):
    default = read(R5 / 'positive/00-profile.json')
    profiles = {}
    for item in read(R5 / 'positive-index.json'):
        profiles[item['profile_sha256']] = read(R5 / 'positive' / (item['stem'] + '-profile.json'))
    cap = read(R5 / 'positive/00-capture.json')
    expected = read(R5 / 'history-results.json')['cases']
    rows = []
    with gzip.open(R5 / 'history-inputs.jsonl.gz', 'rt') as stream:
        for i, line in enumerate(stream):
            if i < start:
                continue
            if i >= stop:
                break
            item = json.loads(line)
            doc = item['input']
            old = item['row']
            assert old == expected[i] and sha(doc) == old['input_sha256']
            current = copy.deepcopy(cap)
            current['record_sha256'] = sha(doc)
            if old['complete']:
                reference = profiles[doc['profile_sha256']]
            else:
                reference = default
            if old['issue'] and old['issue']['code'] == 'independent_profile_required':
                actual = gate.classify(doc, None, gate.load_capture(current, sha(current)))
            else:
                actual = evaluate(doc, reference, current)
            assert actual['records_complete'] is old['complete'], (i, old, actual)
            if not old['complete']:
                incomplete(actual)
                assert actual['reasons']['record'][0]['code'] != 'frozen_record_changed'
            rows.append(dict(index=i, original=old, result=actual))
    write(f'history-{start:05d}-{stop:05d}.json', dict(cases=rows, accepted=sum(r['result']['records_complete'] for r in rows), rejected=sum(not r['result']['records_complete'] for r in rows)))
    print(json.dumps(dict(range=[start, stop], checked=len(rows), accepted=sum(r['result']['records_complete'] for r in rows))))


def cli_case(name):
    case = TMP / ('delivered_00' if name == 'profile_pin' else name)
    profile = read(case / 'profile.json')
    capture = read(case / 'capture.json')
    argv = [str(case / 'record.json'), '--profile', str(case / 'profile.json'),
            '--profile-sha256', '0'*64 if name == 'profile_pin' else sha(profile), '--capture', str(case / 'capture.json'),
            '--capture-sha256', sha(capture)]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = gate.main(argv)
    result = json.loads(output.getvalue())
    write('cli-' + name + '.json', dict(argv=argv, returncode=code, result=result))
    print(output.getvalue(), end='')
    return code


def space():
    mod = load('review_space_source', BASE / 'r6/space_audit.py')
    result = mod.compute()
    original = read(BASE / 'r6/space-results.json')
    assert result == {k: v for k, v in original.items() if k != 'layout'}
    write('space-rerun.json', result)
    print(json.dumps(dict(moved=result['readonly_bank']['total'], parent=result['parent']['selected_parent'], diagnostic=result['diag']['selected_request'])))


def trace():
    generator = load('review_mutation_generator', R5 / 'mutations.py')
    summary = read(R5 / 'mutation-summary.json')
    for key, rel in [('checker_sha256', 'r3/diag_gate.py'), ('derived_contract_sha256', 'r5/derived_contract.py'),
                     ('generator_sha256', 'r5/mutations.py'), ('runner_sha256', 'r5/run_mutations.py'),
                     ('public_runner_sha256', 'r5/public_runner.py')]:
        assert hashlib.sha256((BASE / rel).read_bytes()).hexdigest() == summary[key]
    total = semantic = samples = sample_semantic = 0
    operations = {}
    bases = []
    checked_samples = []
    decoded_hash = hashlib.sha256()
    with gzip.open(R5 / 'mutation-results.jsonl.gz', 'rb') as stream:
        for item, recorded_base in zip(read(R5 / 'positive-index.json'), summary['bases']):
            stem = item['stem']
            doc = read(R5 / 'positive' / (stem + '-record.json'))
            profile = gate.load_profile(read(R5 / 'positive' / (stem + '-profile.json')), item['profile_sha256'])
            raw_cap = read(R5 / 'positive' / (stem + '-capture.json'))
            capture = gate.load_capture(raw_cap, item['capture_sha256'])
            chain = hashlib.sha256()
            local_semantic = local_total = 0
            sampled_ops = set()
            for mutation in generator.generate(doc):
                if mutation.get('summary'):
                    assert mutation['generated'] == recorded_base['mutations'] == local_total
                    assert mutation['counts'] == recorded_base['counts']
                    assert mutation['noops'] == recorded_base['noops']
                    assert chain.hexdigest() == recorded_base['checked_input_chain_sha256']
                    assert local_semantic == recorded_base['semantic_checks']
                    bases.append(dict(base=stem, generated=local_total, regenerated_chain_sha256=chain.hexdigest(),
                                      semantic_trace_rows=local_semantic))
                    break
                line = next(stream)
                decoded_hash.update(line)
                row = json.loads(line)
                assert row['base'] == stem
                assert row['ordinal'] == mutation['ordinal']
                assert row['operation'] == mutation['operation']
                assert row['input_sha256'] == mutation['input_sha256']
                assert json.dumps(row['path']) == json.dumps(mutation['path'])
                assert row['semantic_checked'] is mutation['semantic_reject']
                assert row['api_complete'] is False and row['cli_exit'] == 2
                chain.update(bytes.fromhex(row['input_sha256']))
                operations[row['operation']] = operations.get(row['operation'], 0) + 1
                local_total += 1
                total += 1
                local_semantic += row['semantic_checked']
                semantic += row['semantic_checked']
                if row['operation'] not in sampled_ops or row['ordinal'] % 997 == 0:
                    sampled_ops.add(row['operation'])
                    text = mutation['data'].decode()
                    actual = gate.validate_text(text, profile, capture)
                    incomplete(actual)
                    samples += 1
                    semantic_result = None
                    if row['semantic_checked']:
                        try:
                            changed = gate.parse_json(text)
                            current = copy.deepcopy(raw_cap)
                            current['record_sha256'] = sha(changed)
                            semantic_result = gate.classify(changed, profile, gate.load_capture(current, sha(current)))
                        except gate.InvalidRecord as error:
                            semantic_result = gate.incomplete(error.path, error.code)
                        incomplete(semantic_result)
                        assert semantic_result['reasons']['record'][0]['code'] != 'frozen_record_changed'
                        sample_semantic += 1
                    checked_samples.append(dict(base=stem, ordinal=row['ordinal'], operation=row['operation'],
                                                input_sha256=row['input_sha256'], semantic_result=semantic_result))
            print(json.dumps(dict(trace_bases=len(bases), regenerated=total, sampled=samples)), flush=True)
        assert stream.read() == b''
    assert total == summary['mutants'] == 946577
    assert semantic == summary['semantic_checks_with_updated_record_digest'] == 794044
    assert operations == summary['operations']
    assert decoded_hash.hexdigest() == summary['decoded_trace_sha256']
    result = dict(scope='逐例重建生成输入与归档记录核对；判定器仅作确定性抽查；未重跑全部命令行进程',
                  regenerated=total, semantic_trace_rows=semantic, archived_cli_exit=2,
                  full_cli_rerun=False, sampled_checks=samples, sampled_semantic_checks=sample_semantic,
                  operations=operations, decoded_sha256=decoded_hash.hexdigest(), bases=bases, samples=checked_samples)
    write('mutation-trace-audit.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('bases', 'samples')}, ensure_ascii=False))


if __name__ == '__main__':
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['independent', 'coupled', 'history', 'cli', 'space', 'trace'])
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--stop', type=int, default=8899)
    parser.add_argument('--name')
    args = parser.parse_args()
    started = time.monotonic()
    if args.mode == 'independent':
        independent()
    elif args.mode == 'coupled':
        coupled()
    elif args.mode == 'history':
        history(args.start, args.stop)
    elif args.mode == 'space':
        space()
    elif args.mode == 'trace':
        trace()
    else:
        raise SystemExit(cli_case(args.name))
    print(json.dumps(dict(elapsed_seconds=round(time.monotonic() - started, 3))))
