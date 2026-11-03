"""Recompute review conclusions from the recorded results and raw snapshots."""
import json
from pathlib import Path
import pickle
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
LOCAL = HERE / 'local'


def read(name):
    return json.loads((LOCAL / (name + '.json')).read_text())


def main():
    summary = {}
    rows = json.loads((LOCAL / 'reproduce-hooks.log').read_text())
    results = [{key: value for key, value in row.items() if key not in ('impl', 'batch_stats')} for row in rows]
    assert results[0] == results[1] == results[2]
    summary['previous_reproduction'] = {'equal': True, 'rows': rows}
    for name in ('hook-cases', 'extended-hooks'):
        cases = read(name)['cases']
        equal = {case: row['results']['step'] == row['results']['copy-step'] == row['results']['batch']
                 for case, row in cases.items()}
        assert all(equal.values())
        summary[name] = {'equal': equal, 'passed': sum(equal.values()), 'total': len(equal)}
    forwarding = read('forwarding-hooks')
    found = []
    for name, row in forwarding['cases'].items():
        step, copy, batch = (row['results'][impl] for impl in ('step', 'copy-step', 'batch'))
        assert step == copy and step != batch
        assert step['r0'] == 85 and batch['r0'] == 0
        assert step['ram'] == '00000055' and batch['ram'] == '00000000'
        assert all(result['stop']['reason'] == 'max_steps' for result in (step, copy, batch))
        assert row['stats']['batch'].get('undeclared-hook-steps', 0) == 0
        found.append(name)
    summary['forwarding_hooks'] = {'different_cases': found, 'severity': 'P1', 'closed': False}
    machine = read('machine-forwarding')['results']
    clean = lambda row: {key: value for key, value in row.items() if key != 'batch_stats'}
    assert clean(machine['step']) == clean(machine['copy-step'])
    assert machine['step']['observer_count'] == machine['step']['ram_counter'] == 1000
    assert machine['batch']['observer_count'] == machine['batch']['ram_counter'] == 5
    assert machine['step']['full_snapshot'] != machine['batch']['full_snapshot']
    assert machine['batch']['stop']['reason'] == 'max_steps'
    summary['machine_forwarding'] = {'equal': False, 'steps': 1000,
        'counts': {impl: row['observer_count'] for impl, row in machine.items()},
        'different_memory': machine['step']['memory'] != machine['batch']['memory'],
        'different_full_snapshot': True}
    device_rows = read('device-comparison')['comparisons']
    for row in device_rows:
        case, label = row['case'], row['label']
        states = [pickle.loads((LOCAL / 'device-cases' / impl / (case + '-' + label + '.pkl')).read_bytes())
                  for impl in ('step', 'copy-step', 'batch')]
        assert states[0] == states[1] == states[2]
    summary['device_snapshots'] = {'equal': True, 'points': len(device_rows),
                                   'raw_snapshots': len(device_rows) * 3}
    coverage = read('entry-coverage')
    assert len(coverage['StepHook_calls']) == 5
    assert all(not row['missing_devices'] and all(case['undeclared_propagates'] for case in row['fallbacks'])
               for row in coverage['entries'])
    summary['entry_coverage'] = {'entries': len(coverage['entries']),
        'StepHook_calls': len(coverage['StepHook_calls']),
        'missing_skip_fallback_checks': sum(len(row['fallbacks']) for row in coverage['entries']),
        'missing_devices': []}
    step, batch, variant = (read(name) for name in ('state-step', 'state-batch', 'timer-variant'))
    points = {}
    for target in ('1000000', '10000000'):
        assert step['points'][target] == batch['points'][target]
        points[target] = {'equal': True, 'state': step['points'][target]['state'],
                          'full_snapshot': step['points'][target]['full_snapshot'],
                          'observations': step['points'][target]['observations'],
                          'panel': step['points'][target]['panel']}
    summary['state_comparison'] = points
    assert batch['points']['1000000'] == variant['points']['1000000']
    changed = {key: batch['points']['10000000']['state'][key] != variant['points']['10000000']['state'][key]
               for key in ('cpu', 'memory', 'devices', 'all')}
    changed['full_snapshot'] = batch['points']['10000000']['full_snapshot'] != variant['points']['10000000']['full_snapshot']
    changed['observations'] = batch['points']['10000000']['observations'] != variant['points']['10000000']['observations']
    assert all(changed.values())
    summary['timer_variant'] = {'caught': True, 'equal_at_1000000': True,
        'different_at_10000000': changed, 'variant': variant['variant'],
        'variant_library': variant['library_sha256'], 'batch_library': batch['library_sha256']}
    m2b = read('m2b/m2b-review')
    assert len(m2b['checks']) == 22 and all(m2b['checks'].values())
    assert m2b['card']['native_ready'] and m2b['card']['same_wait_state']
    summary['M2b'] = {'passed': 22, 'total': 22, 'native_ticks': m2b['native_ticks'],
                      'card_wait_state': m2b['card']['same_wait_state']}
    outputs = read('output-cases')
    assert len(outputs['cases']) == 11 and all(row['refused'] for row in outputs['cases'].values())
    positive = read('output-positive')
    assert positive['caller_output_accepted'] and positive['block_write_reopen_equal']
    assert positive['run_stop']['reason'] == 'max_steps' and positive['run_stop']['steps'] == 10000
    summary['outputs'] = {'refusal_checks': 11, 'positive_run_steps': 10000,
                          'block_write_reopen_equal': True}
    summary['verdict'] = '不可以切换'
    summary['P1_01'] = 'OPEN: non-StepHook forwarding layers are skipped'
    summary['P1_02'] = 'PASS: listed undeclared devices cause whole-chain fallback'
    (LOCAL / 'comparisons.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key in
                     ('device_snapshots', 'entry_coverage', 'M2b', 'outputs', 'verdict', 'P1_01', 'P1_02')},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
