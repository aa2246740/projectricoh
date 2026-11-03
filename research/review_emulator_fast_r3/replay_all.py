"""Fresh-process replay of the 71 supplied historical counterexamples."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def jobs():
    rows = []
    for case in ('self-modifying', 'timer-irq-boundaries', 'dma-deadline', 'undeclared-hook',
                 'undeclared-device-method', 'absent-step-hook', 'base-only-step-hook',
                 'retained-mutable-input', 'wide-device-clock', 'bigint-chinese'):
        rows.append(('edge_cases', ['--backend', 'native', '--case', case]))
    rows.append(('preinstalled_overlay', ['--backend', 'native']))
    for case in ('scheduler-dispatch', 'scheduler-class-dispatch', 'tuple-state-alias',
                 'wide-serial-deadline', 'text-clock', 'model-global-type',
                 'snapshot-global-type', 'snapshot-sd-base'):
        rows.append(('new_cases', ['--backend', 'native', '--case', case]))
    rows += [('observer_binding', ['--backend', 'native']), ('snapshot_graph', ['--backend', 'native'])]
    for wrapper in ('before', 'after', 'code-before', 'code-after', 'default-before', 'genuine'):
        rows.append(('extended_cases', ['--backend', 'native', '--wrapper', wrapper]))
    extended = ['duplicate-panel', 'empty-chain', 'internal-alias'] + [
        'retained-' + kind for kind in ('dict', 'list', 'set', 'nested', 'nested-excluded-key', 'bytes', 'record')]
    extended += [field + '-' + str(bits) + '-' + str(sign).replace('-', 'n')
                 for field in ('clock', 'pending') for bits in (63, 64, 127, 128) for sign in (1, -1)]
    rows += [('extended_cases', ['--backend', 'native', '--selection', case]) for case in extended]
    rows += [('additional_cases', ['--backend', 'native', '--case', case]) for case in (
        'nested-key', 'descriptor', 'integer-subclass', 'shared-tuple', 'wrong-base-binding',
        'irq-pending', 'timer-register', 'class-getattribute', 'missing-owner', 'float-clock',
        'custom-list', 'mx-request', 'observer-counter', 'callback-wide-counter')]
    rows += [('hold_bindings', ['--backend', 'native', '--case', case])
             for case in ('inner', 'peer', 'alias', 'genuine')]
    return rows


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    parser = argparse.ArgumentParser(); parser.add_argument('--name', default='old')
    selection = parser.parse_args()
    target = HERE / 'runs' / ('replay-' + selection.name + '.json')
    assert not target.exists()
    result = dict(started=time.strftime('%FT%TZ', time.gmtime()), rows=[])
    for i, (script, args) in enumerate(jobs(), 1):
        name = selection.name + '-' + str(i).zfill(2)
        with (HERE / 'runs' / (name + '.log')).open('x') as log:
            run = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'review.py'),
                                  'replay', name, script, *args], cwd=ROOT,
                                 stdout=log, stderr=subprocess.STDOUT, timeout=300)
        path = HERE / 'runs' / (name + '-verdict.json')
        row = json.loads(path.read_text()) if path.exists() else dict(status='NO_RECEIPT')
        row['returncode'] = run.returncode; result['rows'].append(row)
        target.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(index=i, total=len(jobs()), script=script, args=args,
                              status=row['status'], steps=row.get('steps'), returncode=run.returncode)), flush=True)
    result['counts'] = {s: sum(r['status'] == s for r in result['rows'])
                        for s in sorted({r['status'] for r in result['rows']})}
    result['status'] = 'PASS' if all(r['returncode'] == 0 for r in result['rows']) else 'ERROR'
    target.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
