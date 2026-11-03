"""Recompute equivalence from result contents instead of process exit codes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'local'
EXPECTED = {
    '1000000': '9961a47ff91e318e972a3a712ea2448a51fe0ebd5faa396ee2ce6ab0e2eb88f7',
    '10000000': '84e51c8b3fb0f8b09c0d82c1d63d423fb55b339d001689bf84af7f2e6752f357',
}


def read(name):
    return json.loads((LOCAL / name).read_text())


def main():
    checks, details = {}, {}
    reproduction = read('reproduce-hooks.log')
    checks['reproduce_hooks'] = len(reproduction) == 3 and all(
        row['r0'] == 85 and row['ram'] == '00000055' and row['hook_steps'] == list(range(8))
        and row['stop'] == reproduction[0]['stop'] for row in reproduction)
    for filename in ('forwarding-hooks.json', 'extended-hooks.json', 'independent-hooks.json', 'hook-cases.json'):
        result = read(filename)
        values = {}
        for name, case in result['cases'].items():
            rows = case['results']
            values[name] = rows['step'] == rows['copy-step'] == rows['batch']
        checks[filename] = all(values.values())
        details[filename] = values
    machine = read('machine-forwarding.json')['results']
    clean = lambda row: {key: value for key, value in row.items() if key != 'batch_stats'}
    checks['machine_forwarding'] = (clean(machine['step']) == clean(machine['copy-step']) == clean(machine['batch'])
                                    and all(row['observer_count'] == row['ram_counter'] == 1000 for row in machine.values()))
    state_step, state_batch = read('state-step.json'), read('state-batch.json')
    checks['state_runs_complete'] = state_step['status'] == state_batch['status'] == 'complete'
    for point, digest in EXPECTED.items():
        first, second = state_step['points'][point], state_batch['points'][point]
        checks['state_' + point] = first == second and first['state']['all'] == digest
        details['state_' + point] = {'equal': first == second, 'state_hash': first['state'],
                                    'full_snapshot': first['full_snapshot'],
                                    'observations': first['observations'], 'panel': first['panel']}
    checks['state_batch_executed'] = (state_batch['batch_stats']['batch-steps'] > 9000000
                                      and state_batch['batch_stats'].get('undeclared-hook-steps', 0) == 0)
    m2b = read('m2b/m2b-review.json')
    checks['m2b'] = m2b['status'] == 'passed' and m2b['passed'] == m2b['total'] == 22 and all(m2b['checks'].values())
    checks['m2b_card_wait'] = m2b['card']['same_wait_state'] and m2b['card']['native_ready']
    cold, stable, card = (read('m2b/' + name + '-review.json') for name in ('cold', 'stable', 'card'))
    checks['m2b_card_run_complete'] = card['steps'] == 55000000 and card['stop']['reason'] == 'max_steps'
    checks['m2b_native_ticks'] = len(m2b['native_ticks']) == 2 and m2b['native_ticks'][1] > m2b['native_ticks'][0]
    checks['m2b_long_runs_use_batch'] = all(row.get('batch-steps', 0) > 4000000 and
                                            row.get('undeclared-hook-steps', 0) == 0 for row in m2b['batch_stats'][:3])
    entries = read('entry-paths.json')
    checks['entry_paths'] = len(entries['entries']) == 7 and all(row['passed'] and row['nice'] == 15 for row in entries['entries'])
    details['m2b'] = {'passed': m2b['passed'], 'total': m2b['total'], 'native_ticks': m2b['native_ticks'],
                      'card_wait': m2b['card']['same_wait_state'],
                      'steps': [cold['steps'], stable['steps'], card['steps']]}
    processes = {path.name: json.loads(path.read_text()) for path in sorted(LOCAL.glob('*-process.json'))}
    simulation_names = ('reproduce-hooks', 'forwarding-hooks', 'machine-forwarding', 'extended-hooks',
                        'independent-hooks', 'hook-cases', 'state-step', 'state-batch', 'm2b', 'entry-paths')
    checks['simulation_processes'] = all(processes[name + '-process.json']['returncode'] == 0 and
                                         processes[name + '-process.json']['nice'] == 15 for name in simulation_names)
    # A fixed 50M-step reference takes 1040 seconds; limits leave more than 3x that budget.
    checks['long_timeouts'] = all(processes[name]['timeout_seconds'] >= 3120 for name in
                                   ('state-step-process.json', 'state-batch-process.json', 'm2b-process.json'))
    evidence = [path for path in LOCAL.rglob('*.json') if path.name not in
                ('comparisons.json', 'inputs-before.json', 'inputs-after.json', 'cleanup.json')]
    result = {'passed': all(checks.values()), 'checks': checks, 'details': details,
              'processes': processes,
              'review_infrastructure_failures': {name: row for name, row in processes.items()
                                                 if row['returncode'] != 0 and
                                                 name not in {item + '-process.json' for item in simulation_names}},
              'evidence_sha256': {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in sorted(evidence)}}
    (LOCAL / 'comparisons.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'checks': len(checks),
                      'failed': [name for name, value in checks.items() if not value]}))
    assert result['passed']


if __name__ == '__main__':
    main()
