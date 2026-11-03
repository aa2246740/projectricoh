"""Independent cold-start state comparison at fixed instruction counts."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
impl = sys.argv[1]
TOOLS = ROOT / ('tools/gxr_emulator' if impl == 'step' else 'tools/gxr_emulator_batch')
sys.path.insert(0, str(TOOLS))
import speed_snapshot as snap


def main():
    machine = snap.Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    if impl == 'batch':
        cpu.set_batch(True)
    snap.attach_panel(machine)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    snap.set_dial(cpu, machine.devices, 2)
    result = {'impl': impl, 'library_sha256': snap.sha(TOOLS / 'build/libgxr_m32r.dylib'),
              'points': {}}
    try:
        for target in [1000000, 10000000]:
            stop = cpu.run(target - cpu.steps)
            assert stop.reason == 'max_steps' and cpu.steps == target, stop.to_dict()
            state = cpu.snapshot()
            result['points'][str(target)] = {
                'state': snap.state_hash(machine),
                'full_snapshot': snap.value_hash(state),
                'observations': snap.value_hash(snap.observer_data(machine)),
                'memory_regions': [{'base': base, 'length': len(data), 'writable': writable,
                                    'sha256': hashlib.sha256(data).hexdigest()}
                                   for base, data, writable in state['regions']],
                'device_types': state['device_types']}
            print(json.dumps({'impl': impl, 'steps': target,
                              'state': result['points'][str(target)]['state']['all']}), flush=True)
        result['batch_stats'] = dict(getattr(cpu, 'batch_stats', {}))
        result['status'] = 'complete'
    finally:
        machine.close()
        (HERE / 'local' / ('state-' + impl + '.json')).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
