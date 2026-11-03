#!/usr/bin/env python3
"""Evaluate named MAIN and continuation artifacts against M2b criteria."""
import argparse
import hashlib
import json
from pathlib import Path
import pickle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT/'tools/gxr_emulator'
OUT = HERE/'local'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def load(name):
    path = OUT/(name+'.json')
    return json.loads(path.read_text()), {'file': path.name, 'sha256': digest(path)}


def checkpoint(name):
    path = OUT/(name+'-stop.pkl')
    metadata = json.loads(path.with_suffix('.json').read_text())
    assert digest(path) == metadata['sha256'], path
    state = pickle.loads(path.read_bytes())
    def integer(address, size=4):
        for base, data, _ in state['regions']:
            if base <= address and address+size <= base+len(data):
                return int.from_bytes(data[address-base:address-base+size], 'big')
        raise ValueError(f'missing checkpoint memory {address:#x}')
    return {'file': path.name, 'sha256': metadata['sha256'],
            'rtos_tick': integer(0x200d183c), 'current_task': integer(0x200d1838, 2),
            'states': {task: integer(0x200d2594+4*(task-1)) for task in (6, 8, 28)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cold', required=True)
    parser.add_argument('--stable', required=True)
    parser.add_argument('--board-checks', required=True)
    parser.add_argument('--regression', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if any(Path(value).name != value for value in vars(args).values()):
        parser.error('simple local evidence names required')
    target = OUT/(args.output+'.json')
    if target.exists():
        parser.error('choose a fresh evidence name')
    cold, cold_id = load(args.cold)
    stable, stable_id = load(args.stable)
    board, board_id = load(args.board_checks)
    regression, regression_id = load(args.regression)
    cold_memory, stable_memory = checkpoint(args.cold), checkpoint(args.stable)
    observed = cold['observations']
    checks = {}
    checks['official_MAIN'] = cold['start_step'] == 0 and cold['start_checkpoint'] is None \
        and cold['image'] == 'official' and cold['image_sha256'] == \
        'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    checks['bounded_runs_without_fault'] = all(row['stop']['reason'] == 'max_steps'
                                                for row in (cold, stable))
    sources = {path.name: digest(path) for path in TOOLS.glob('*.py')}
    checks['current_MAIN_and_board_sources'] = all(row['source_hashes'] == sources
                                                   for row in (cold, stable, board))
    checks['same_frozen_library'] = all(row['library_sha256'] == cold['library_sha256']
                                      for row in (stable, regression)) and \
        digest(TOOLS/'build/libgxr_m32r.dylib') == cold['library_sha256']
    checks['continuation_identity'] = stable['start_step'] == cold['steps'] and \
        stable['start_checkpoint'] == {'file': cold_memory['file'],
                                      'sha256': cold_memory['sha256']}
    checks['stable_native_tick_window'] = stable['steps']-stable['start_step'] >= 2000000 \
        and stable_memory['rtos_tick'] > cold_memory['rtos_tick'] \
        and stable['observations']['event_counts'].get('rtos-tick', 0) > 1
    checks['shared_initializers'] = len(observed['drivers']) == 41 and \
        all(row.get('result') == 0 for row in observed['drivers'].values())
    checks['component_initializers'] = len(observed['components']) == 8 and \
        all(row.get('result') == 0 for row in observed['components'].values())
    checks['Task6_UI_initialization'] = len(observed['ui_initializers']) == 3 and \
        all(row.get('result') == 0 for row in observed['ui_initializers'].values()) and \
        any(row['task'] == 6 for row in observed['ui_loop_entries'])
    checks['Task6_native_creation'] = observed['created_tasks'].get('6', {}).get('result') == 0
    for task, queue in ((8, 2), (28, 15)):
        task_row = observed['created_tasks'].get(str(task), {})
        checks[f'Task{task}_native_creation_and_scheduling'] = task_row.get('result') == 0 \
            and observed['entry_hits'].get(str(task), 0) > 0 \
            and observed['scheduled'].get(str(task), 0) > 1 \
            and observed['task_entry_records'].get(str(task), {}).get('current_task') == task
        queue_row = observed['created_queues'].get(str(queue), {})
        checks[f'queue{queue}_native_creation'] = queue_row.get('result') == 0
        for label, run in (('cold', cold), ('stable', stable)):
            last = run['observations']['last_services'].get(str(task), {})
            wait = run['observations']['queue_waits'].get(str(task), {})
            # A resumed observer can see a task stay parked without a second
            # receive call. In that case the cold native wait and unchanged
            # RTOS wait state are the evidence, not a fabricated new request.
            memory = stable_memory if label == 'stable' else cold_memory
            if label == 'stable' and not wait:
                parked = stable_memory['states'][task] == cold_memory['states'][task] \
                    and bool(stable_memory['states'][task] & 0x200)
            else:
                # A cyclic callback may run while this task is parked and
                # overwrite last_services under the interrupted task ID.
                parked = wait.get('queue_id') == queue and wait.get('wait', 0) != 0 \
                    and bool(memory['states'][task] & 0x200)
            checks[f'Task{task}_{label}_native_message_wait'] = parked
    masks = [row['mask'] for row in cold['board_events']
             if row['kind'] == 'unit-ready-queued']
    checks['diagnostic_ready_disabled'] = not cold['arguments'].get('synthetic_unit_ready') \
        and masks == []
    readiness = [row for row in observed.get('startup_ready_services', [])
                 if row['service'] == 144 and row['args'][0] == 1]
    checks['native_startup_ready_observed'] = all(any(
        row['task'] == task and row['args'][1] == mask and row['psw'] & 0x80
        for row in readiness) for mask, task in
        ((0x00800000, 8), (0x02000000, 9), (0x04000000, 10)))
    checks['ordinary_device_clock'] = not cold['idle_tick_enabled'] \
        and not stable['idle_tick_enabled']
    checks['board_and_native_regressions'] = board['status'] == regression['status'] == 'PASS'
    optional_ui_wait = observed['queue_waits'].get('6')
    result = {'milestone': 'M2b', 'status': 'PASS' if all(checks.values()) else 'INCOMPLETE',
              'checks': checks, 'runs': [cold_id, stable_id],
              'test_inputs': [board_id, regression_id],
              'checkpoints': [cold_memory, stable_memory],
              'Task6_message_wait': optional_ui_wait,
              'Task6_last_service': stable['observations']['last_services'].get('6'),
              'native_startup_ready_sources': readiness,
              'task_creation': {task: observed['created_tasks'].get(str(task))
                                for task in (6, 8, 28)},
              'queues': {queue: observed['created_queues'].get(str(queue)) for queue in (2, 15)},
              'cold_schedules': {task: observed['scheduled'].get(str(task), 0)
                                  for task in (6, 8, 28)},
              'stable_schedules': {task: stable['observations']['scheduled'].get(str(task), 0)
                                    for task in (6, 8, 28)},
              'scope': 'Original firmware control flow under declared board inputs and unit/ISP stubs; '
                       'no card, camera, image capture, physical timing or storage-flow acceptance.',
              'runner_sha256': digest(Path(__file__))}
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
