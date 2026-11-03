"""Check actual production hook types and record a single storage entry timing."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / 'tools/gxr_emulator_batch'
ENTRIES = ('devices', 'storage', 'panel', 'm2_checks', 'm2_base', 'm2_board', 'panel_function')
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()


def worker(entry):
    sys.path.insert(0, str(TOOLS))
    import backend
    cpus, runs = [], []
    original_init, original_run = backend.Backend.__init__, backend.Backend.run
    def initialize(cpu, **kwargs):
        original_init(cpu, **kwargs)
        cpu.set_mode('fast')
        cpu.set_batch(True)
        cpus.append(cpu)
    def measured(cpu, budget):
        layers, hook = [], cpu.step_hook
        while hook is not None:
            exact = type(hook) is backend.StepHook
            layers.append({'type': type(hook).__qualname__, 'exact_StepHook': exact,
                           'step': hook.step.__qualname__ if exact else None,
                           'devices': [type(d).__qualname__ for d in hook.devices()] if exact else []})
            hook = hook.previous if exact else None
        plan = backend.declared_plan(cpu.step_hook, cpu)
        before = dict(cpu.batch_stats)
        start_step = cpu.steps
        started = time.monotonic()
        stop = original_run(cpu, budget)
        seconds = time.monotonic() - started
        runs.append({'layers': layers, 'plan_declared': plan is not None,
                     'start_step': start_step, 'end_step': cpu.steps, 'budget': budget,
                     'seconds': seconds, 'stop': stop.to_dict(),
                     'stats': {key: value - before.get(key, 0) for key, value in cpu.batch_stats.items()}})
        return stop
    backend.Backend.__init__, backend.Backend.run = initialize, measured
    target = HERE / 'local/entry-paths' / entry
    target.mkdir(parents=True, exist_ok=True)
    if entry == 'devices':
        from image import Image
        from devices import install
        cpu = backend.Backend()
        Image().load(cpu)
        install(cpu)
        try:
            cpu.run(10000)
        finally:
            cpu.close()
    elif entry in ('storage', 'panel', 'panel_function'):
        import storage_run
        if entry == 'storage':
            # Exercise the real run() path, including its result and checkpoint writes.
            storage_run.OUT = target
            started = time.monotonic()
            storage_run.run(SimpleNamespace(name='storage-timing', card=None, resume=None,
                                           budget=5000000, card_event=False, stop_at=[], task=None))
            end_to_end = time.monotonic() - started
        elif entry == 'panel':
            import speed_snapshot
            machine = storage_run.Machine()
            speed_snapshot.attach_panel(machine)
            try:
                machine.cpu.run(10000)
            finally:
                machine.close()
        else:
            # Same panel hook shape as unit28_stock/emu_g146_hooks.py:81-86.
            from panel import Panel
            machine = storage_run.Machine()
            panel = Panel(machine.cpu, machine.devices)
            previous = machine.cpu.step_hook
            def step(cpu):
                panel.advance()
                previous(cpu)
            machine.cpu.step_hook = step
            try:
                machine.cpu.run(10000)
            finally:
                machine.close()
    elif entry == 'm2_checks':
        import m2_checks
        cpu, devices = m2_checks.restored('baseline-task1.pkl')
        try:
            cpu.run(10000)
        finally:
            cpu.close()
    else:
        import m2
        sys.argv = [str(TOOLS / 'm2.py'), '--budget', '10000', '--name', entry,
                    '--output-dir', str(target)]
        if entry == 'm2_board':
            sys.argv.append('--board-m2b')
        m2.main()
    assert len(cpus) == 1 and runs
    if entry == 'panel_function':
        passed = all(not row['plan_declared'] and row['layers'][0]['type'] == 'function'
                     and row['stats'].get('batch-steps', 0) == 0
                     and row['stats'].get('undeclared-hook-steps', 0) == row['budget'] == 10000
                     and row['stop']['reason'] == 'max_steps' for row in runs)
    else:
        passed = all(row['plan_declared'] and all(layer['exact_StepHook'] for layer in row['layers'])
                     and row['stats'].get('batch-steps', 0) > 0
                     and row['stats'].get('undeclared-hook-steps', 0) == 0
                     and row['stop']['reason'] == 'max_steps' for row in runs)
    record = {'entry': entry, 'nice': os.getpriority(os.PRIO_PROCESS, 0), 'runs': runs,
              'expected_fallback': entry == 'panel_function', 'passed': passed}
    if entry == 'storage':
        record.update(end_to_end_seconds=end_to_end, timing_repetitions=1,
                      timed_steps=sum(row['end_step'] - row['start_step'] for row in runs),
                      run_seconds=sum(row['seconds'] for row in runs))
    (target / 'types.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'entry': entry, 'passed': record['passed'], 'runs': len(runs),
                      'batch_steps': sum(row['stats'].get('batch-steps', 0) for row in runs)}), flush=True)
    assert record['passed']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=ENTRIES)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    records = []
    for entry in ENTRIES:
        result = subprocess.run([sys.executable, '-I', '-B', __file__, '--worker', entry],
                                cwd=ROOT, timeout=3600, capture_output=True, text=True)
        print(result.stdout, end='', flush=True)
        if result.returncode:
            print(result.stderr, end='', flush=True)
            raise SystemExit(result.returncode)
        records.append(json.loads((HERE / 'local/entry-paths' / entry / 'types.json').read_text()))
    summary = {'entries': records, 'passed': all(row['passed'] for row in records)}
    (HERE / 'local/entry-paths.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
