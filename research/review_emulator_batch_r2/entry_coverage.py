"""Record actual advance calls and check each entry's device declarations."""
import argparse
import ast
import importlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / 'tools/gxr_emulator_batch'
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
ENTRIES = ('storage', 'panel', 'm2_checks', 'm2_base', 'm2_board')


def worker(entry):
    sys.path.insert(0, str(TOOLS))
    import backend
    modules = [importlib.import_module(name) for name in
               ('devices', 'peripherals', 'board', 'sdcard', 'panel')]
    actual, methods, cpus = {}, {}, []
    for module in modules:
        for cls in vars(module).values():
            if not isinstance(cls, type) or cls.__module__ != module.__name__:
                continue
            for name in ('advance', 'advance_irq'):
                if name not in cls.__dict__:
                    continue
                original = getattr(cls, name)
                def called(device, *args, original=original, name=name, **kwargs):
                    actual[id(device)] = device
                    methods.setdefault(id(device), set()).add(type(device).__name__ + '.' + name)
                    return original(device, *args, **kwargs)
                setattr(cls, name, called)
    original_init = backend.Backend.__init__
    def initialize(cpu, **kwargs):
        original_init(cpu, **kwargs)
        cpu.set_mode('fast')
        cpu.set_batch(False)
        cpus.append(cpu)
    backend.Backend.__init__ = initialize
    target = HERE / 'local/entry-coverage' / entry
    target.mkdir(parents=True, exist_ok=True)
    if entry in ('storage', 'panel'):
        import storage_run
        machine = storage_run.Machine()
        if entry == 'panel':
            import speed_snapshot
            speed_snapshot.attach_panel(machine)
        actual.clear()
        methods.clear()
        stop = machine.cpu.run(8)
    elif entry == 'm2_checks':
        import m2_checks
        cpu, devices = m2_checks.restored('baseline-task1.pkl')
        actual.clear()
        methods.clear()
        stop = cpu.run(8)
    else:
        import m2
        sys.argv = [str(TOOLS / 'm2.py'), '--budget', '8', '--name', entry,
                    '--output-dir', str(target)]
        if entry == 'm2_board':
            sys.argv.append('--board-m2b')
        if entry == 'm1a':
            sys.argv += ['--profile', 'm1a']
        actual.clear()
        methods.clear()
        m2.main()
        stop = None
    assert len(cpus) == 1
    cpu = cpus[0]
    declared, layers = {}, []
    hook = cpu.step_hook
    while hook is not None:
        assert isinstance(hook, backend.StepHook)
        devices = tuple(hook.devices())
        declared.update((id(device), device) for device in devices)
        layers.append({'step': hook.step.__qualname__,
                       'devices': [type(device).__name__ for device in devices]})
        hook = hook.previous
    missing = [type(device).__name__ for key, device in actual.items() if key not in declared]
    fallbacks = []
    for key, device in actual.items():
        previous = device.__dict__.get('batch_skip', 'absent')
        device.batch_skip = None
        try:
            # m2.run already closed its CPU, but plans inspect only Python state.
            propagated = cpu.step_hook.batch_plan(cpu) is None
        finally:
            if previous == 'absent':
                del device.batch_skip
            else:
                device.batch_skip = previous
        fallbacks.append({'device': type(device).__name__, 'undeclared_propagates': propagated})
    record = {'entry': entry, 'stop': stop.to_dict() if stop else None, 'layers': layers,
              'actual_methods': sorted({method for values in methods.values() for method in values}),
              'actual_devices': sorted(type(device).__name__ for device in actual.values()),
              'missing_devices': missing, 'fallbacks': fallbacks,
              'passed': not missing and all(row['undeclared_propagates'] for row in fallbacks)}
    (target / 'coverage.json').write_text(json.dumps(record, indent=2) + '\n')
    if cpu.handle:
        cpu.close()
    print(json.dumps(record), flush=True)
    assert record['passed']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=ENTRIES)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    records = []
    for entry in ENTRIES:
        process = subprocess.run([sys.executable, '-I', '-B', __file__, '--worker', entry],
                                 cwd=ROOT, timeout=1800, capture_output=True, text=True)
        print(process.stdout, end='', flush=True)
        if process.returncode:
            print(process.stderr, end='', flush=True)
            raise SystemExit(process.returncode)
        records.append(json.loads((HERE / 'local/entry-coverage' / entry / 'coverage.json').read_text()))
    static = []
    for path in sorted(TOOLS.glob('*.py')):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'StepHook':
                static.append({'path': str(path.relative_to(ROOT)), 'line': node.lineno,
                               'source': ast.get_source_segment(source, node),
                               'has_devices': any(keyword.arg == 'devices' for keyword in node.keywords)})
    assert all(row['has_devices'] for row in static)
    result = {'entries': records, 'StepHook_calls': static, 'passed': all(row['passed'] for row in records)}
    (HERE / 'local/entry-coverage.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'entries': len(records), 'StepHook_calls': len(static), 'passed': result['passed']}))


if __name__ == '__main__':
    main()
