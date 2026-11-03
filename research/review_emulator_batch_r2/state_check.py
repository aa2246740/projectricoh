"""Cold MAIN comparison, including a timer plan variant on the current source."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--impl', choices=('step', 'copy-step', 'batch'), required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--timer-variant', action='store_true')
    args = parser.parse_args()
    tools = ROOT / ('tools/gxr_emulator' if args.impl == 'step' else 'tools/gxr_emulator_batch')
    sys.path.insert(0, str(tools))
    variant = None
    if args.timer_variant:
        assert args.impl == 'batch'
        source = (tools / 'devices.py').read_text()
        tree = ast.parse(source)
        timer = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Timer')
        plan = next(node for node in timer.body if isinstance(node, ast.FunctionDef) and node.name == 'batch_plan')
        lines = source.splitlines(True)
        revised = ''.join(lines[:plan.lineno-1]) + '    def batch_plan(self):\n        return NEVER\n'
        revised += ''.join(lines[plan.end_lineno:])
        directory = HERE / 'local/timer-variant'
        directory.mkdir(exist_ok=True)
        target = directory / 'devices.py'
        target.write_text(revised)
        variant = {'original_sha256': hashlib.sha256(source.encode()).hexdigest(),
                   'variant_sha256': hashlib.sha256(revised.encode()).hexdigest(),
                   'changed_method': 'Timer.batch_plan', 'behavior': 'return NEVER'}
        spec = importlib.util.spec_from_file_location('devices', target)
        module = importlib.util.module_from_spec(spec)
        sys.modules['devices'] = module
        spec.loader.exec_module(module)
    import speed_snapshot as snap
    machine = snap.Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    if args.impl != 'step':
        cpu.set_batch(args.impl == 'batch')
    snap.attach_panel(machine)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    snap.set_dial(cpu, machine.devices, 2)
    result = {'impl': args.impl, 'variant': variant, 'points': {},
              'library_sha256': snap.sha(tools / 'build/libgxr_m32r.dylib')}
    try:
        for target in (1000000, 10000000):
            stop = cpu.run(target - cpu.steps)
            assert stop.reason == 'max_steps' and cpu.steps == target, stop.to_dict()
            state = cpu.snapshot()
            result['points'][str(target)] = {
                'stop': stop.to_dict(), 'state': snap.state_hash(machine),
                'full_snapshot': snap.value_hash(state),
                'observations': snap.value_hash(snap.observer_data(machine)),
                'panel': snap.value_hash({'down': machine.panel.down, 'events': machine.panel.events,
                                          'records': machine.panel.records, 'pin_bytes': machine.panel.pin_bytes}),
                'regions': [{'base': base, 'length': len(data), 'writable': writable,
                             'sha256': hashlib.sha256(data).hexdigest()} for base, data, writable in state['regions']],
                'device_types': state['device_types'],
                'timer': {'counter': machine.devices['timer'].counter,
                          'expirations': machine.devices['timer'].expirations,
                          'regs': [{'address': key[0], 'size': key[1], 'value': value}
                                   for key, value in sorted(machine.devices['timer'].regs.items())]}}
            print(json.dumps({'impl': args.impl, 'steps': target, 'variant': bool(variant),
                              'state': result['points'][str(target)]['state']['all']}), flush=True)
        result['batch_stats'] = dict(getattr(cpu, 'batch_stats', {}))
        result['status'] = 'complete'
    finally:
        machine.close()
        (HERE / 'local' / (args.name + '.json')).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
