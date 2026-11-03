"""Exercise the forwarding-hook case on the current cold MAIN Machine."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
IMPLS = ('step', 'copy-step', 'batch')


def worker(impl):
    tools = ROOT / ('tools/gxr_emulator' if impl == 'step' else 'tools/gxr_emulator_batch')
    sys.path.insert(0, str(tools))
    import storage_run
    import speed_snapshot as snap
    machine = storage_run.Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    if impl != 'step':
        cpu.set_batch(impl == 'batch')
    class ForwardingHook:
        def __init__(self, inner):
            self.inner, self.count = inner, 0

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def __call__(self, machine_cpu):
            self.count += 1
            machine_cpu.write(0x27fff000, self.count.to_bytes(4, 'big'))
            self.inner(machine_cpu)

    observer = ForwardingHook(cpu.step_hook)
    cpu.step_hook = observer
    try:
        stop = cpu.run(1000)
        state = cpu.snapshot()
        result = {'stop': stop.to_dict(), 'observer_count': observer.count,
                  'ram_counter': int.from_bytes(cpu.read(0x27fff000, 4), 'big'),
                  'full_snapshot': snap.value_hash(state),
                  'registers': snap.value_hash(state['registers']),
                  'memory': snap.value_hash(state['regions']),
                  'devices': snap.value_hash(state['devices']),
                  'observations': snap.value_hash(snap.observer_data(machine)),
                  'batch_stats': dict(getattr(cpu, 'batch_stats', {}))}
        assert stop.reason == 'max_steps' and cpu.steps == 1000
        (HERE / 'local' / ('machine-forwarding-' + impl + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        machine.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=IMPLS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    rows = {}
    for impl in IMPLS:
        process = subprocess.run([sys.executable, '-I', '-B', __file__, '--worker', impl],
                                 cwd=ROOT, timeout=1800, capture_output=True, text=True)
        print(process.stdout, end='', flush=True)
        if process.returncode:
            print(process.stderr, end='', flush=True)
            raise SystemExit(process.returncode)
        rows[impl] = json.loads((HERE / 'local' / ('machine-forwarding-' + impl + '.json')).read_text())
    clean = lambda row: {key: value for key, value in row.items() if key != 'batch_stats'}
    assert clean(rows['step']) == clean(rows['copy-step'])
    assert rows['step']['observer_count'] == rows['step']['ram_counter'] == 1000
    different = clean(rows['step']) != clean(rows['batch'])
    result = {'results': rows, 'equivalent': not different}
    (HERE / 'local/machine-forwarding.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'equivalent': not different, 'counts': {impl: row['observer_count'] for impl, row in rows.items()}}))


if __name__ == '__main__':
    main()
