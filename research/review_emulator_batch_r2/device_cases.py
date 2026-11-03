"""Complete-snapshot comparisons at four devices' state transitions."""
import argparse
import json
from pathlib import Path
import pickle
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
    import backend
    from board import SioTransmit, I2cRegisters
    from devices import InterruptController, GPIO
    from image import Image
    from panel import Panel
    from peripherals import StartupRegisters
    from speed_snapshot import value_hash
    directory = HERE / 'local/device-cases' / impl
    directory.mkdir(parents=True, exist_ok=True)
    result = {'impl': impl, 'cases': {}}

    def base():
        cpu = backend.Backend(mode='fast')
        if impl != 'step':
            cpu.set_batch(impl == 'batch')
        cpu.map(0x1000, bytes.fromhex('70007000') * 256)
        cpu.map(0x0500221c, bytes.fromhex('70007000') * 64)
        cpu.map(0x8000, bytes(0x2000))
        cpu.set_reg('pc', 0x1000)
        cpu.set_reg('spi', 0x8080)
        cpu.set_reg('spu', 0x9080)
        return cpu

    def save(cpu, case, label, panel=None, stop=None):
        state = {'cpu': cpu.snapshot()}
        if panel:
            state['panel'] = {key: value for key, value in panel.__dict__.items() if key not in ('cpu', 'devices')}
        if stop:
            state['stop'] = stop.to_dict()
        target = directory / (case + '-' + label + '.pkl')
        target.write_bytes(pickle.dumps(state, protocol=4))
        result['cases'].setdefault(case, []).append({'label': label, 'steps': cpu.steps,
            'state_hash': value_hash(state), 'snapshot': str(target.relative_to(ROOT))})

    def hook(cpu, step, plan, devices, skip):
        cpu.step_hook = step if impl == 'step' else backend.StepHook(step, plan, skip, devices=lambda: devices)

    for case in ('sio2_completion_and_enable', 'sio2_in_service'):
        cpu = base()
        irq, startup, sio = InterruptController(), StartupRegisters(), SioTransmit()
        irq.attach(cpu, [(0xff401000, 0xff402000)])
        startup.attach(cpu, [])
        sio.attach(cpu, [(0xff703208, 0xff70320c), (0xff70321a, 0xff70321c)])
        devices = {'irq': irq, 'startup': startup}
        def step(machine):
            sio.advance(devices)
            irq.advance(machine)
        hook(cpu, step, lambda machine: (sio.batch_plan(devices), irq.batch_armed(), frozenset()),
             (sio, irq), lambda machine, n: (sio.batch_skip(n), irq.batch_skip(n)))
        irq.regs[(0xff401040 + 4 * 91, 2)] = 0
        if case == 'sio2_in_service':
            startup.regs[0xff70320f] = 4
            irq.in_service = 91
        cpu.write(0xff70321a, bytes.fromhex('0055'))
        try:
            save(cpu, case, 'queued')
            for count, label in ((7, 'before_deadline'), (1, 'at_deadline'), (1, 'completed')):
                stop = cpu.run(count)
                assert stop.reason == 'max_steps'
                save(cpu, case, label, stop=stop)
            assert sio.pending is None and sio.irq_pending
            startup.regs[0xff70320f] = 4
            if case == 'sio2_in_service':
                cpu.write(0xff401008, bytes(4))
            stop = cpu.run(1)
            assert list(irq.pending) == [91] and not sio.irq_pending
            save(cpu, case, 'irq_enabled', stop=stop)
            result['cases'][case][-1]['batch_stats'] = dict(getattr(cpu, 'batch_stats', {}))
        finally:
            cpu.close()

    cpu = base()
    irq, i2c = InterruptController(), I2cRegisters()
    irq.attach(cpu, [(0xff401000, 0xff402000)])
    i2c.attach(cpu, [(0xff70c000, 0xff70c038)])
    devices = {'irq': irq}
    def step(machine):
        i2c.advance(devices)
        irq.advance(machine)
    hook(cpu, step, lambda machine: (i2c.batch_plan(devices), irq.batch_armed(), frozenset()),
         (i2c, irq), lambda machine, n: (i2c.batch_skip(n), irq.batch_skip(n)))
    def write(offset, value):
        cpu.write(0xff70c000 + offset, value.to_bytes(4, 'big'))
    def run_i2c(count, label, reason='max_steps'):
        stop = cpu.run(count)
        assert stop.reason == reason, stop.to_dict()
        save(cpu, 'i2c_register_flow', label, stop=stop)
    try:
        write(0x20, 0x72)
        write(0x10, 1)
        save(cpu, 'i2c_register_flow', 'start_queued')
        run_i2c(7, 'start_before_deadline')
        run_i2c(1, 'start_at_deadline')
        run_i2c(1, 'start_completed')
        assert i2c.pending is None and list(irq.pending) == [103]
        irq.pending.clear()
        irq.in_service = 103
        write(0x20, 0x41)
        write(0x14, 1)
        run_i2c(8, 'select_at_deadline')
        run_i2c(4, 'select_waits_for_eoi')
        assert i2c.pending is not None and i2c.selector is None
        cpu.write(0xff401008, bytes(4))
        run_i2c(1, 'select_completed_after_eoi')
        assert i2c.selector == 0x41
        write(0x20, 0x55)
        write(0x14, 1)
        run_i2c(8, 'write_at_deadline')
        run_i2c(1, 'write_completed')
        assert i2c.registers[0x41] == 0x55 and i2c.selector == 0x42
        write(0x20, 0x73)
        write(0x10, 1)
        run_i2c(9, 'read_start_completed')
        write(0x14, 1)
        run_i2c(8, 'receive_at_deadline')
        run_i2c(1, 'receive_completed')
        assert cpu.read(0xff70c020, 4) == bytes(4) and i2c.selector == 0x43
        save(cpu, 'i2c_register_flow', 'register_read')
        write(0x14, 1)
        write(0x20, 1)
        run_i2c(8, 'invalid_direction_at_deadline')
        run_i2c(1, 'invalid_direction_rejected', 'fault')
        write(0x10, 2)
        run_i2c(8, 'stop_at_deadline')
        run_i2c(1, 'stop_completed')
        assert not i2c.active and i2c.pending is None
    finally:
        cpu.close()

    cpu = base()
    irq = InterruptController()
    irq.attach(cpu, [(0xff401000, 0xff402000)])
    hook(cpu, lambda machine: irq.advance(machine),
         lambda machine: (irq.batch_plan(), irq.batch_armed(), frozenset()),
         (irq,), lambda machine, n: irq.batch_skip(n))
    try:
        irq.raise_irq(65)
        stop = cpu.run(3)
        assert irq.delivered == 0
        save(cpu, 'irq_entry', 'ie_clear', stop=stop)
        cpu.set_reg('psw', 0x40)
        cpu.set_reg('pc', 0x1002)
        stop = cpu.run(1)
        assert irq.delivered == 0
        save(cpu, 'irq_entry', 'right_half', stop=stop)
        stop = cpu.run(1)
        assert irq.delivered == 1 and irq.in_service == 65
        save(cpu, 'irq_entry', 'word_boundary_delivery', stop=stop)
        irq.raise_irq(66)
        cpu.set_reg('psw', 0x40)
        cpu.set_reg('pc', 0x1000)
        stop = cpu.run(4)
        assert irq.delivered == 1
        save(cpu, 'irq_entry', 'in_service_defers', stop=stop)
        cpu.write(0xff401008, bytes(4))
        stop = cpu.run(1)
        assert irq.delivered == 2 and irq.in_service == 66
        save(cpu, 'irq_entry', 'eoi_allows_next', stop=stop)
    finally:
        cpu.close()

    cpu = base()
    cpu.image = Image('official')
    gpio = GPIO()
    gpio.attach(cpu, [(0xff704000, 0xff704100)])
    panel = Panel(cpu, {'gpio': gpio})
    cpu.step_hook = lambda machine: None
    if impl == 'step':
        cpu.step_hook = lambda machine: panel.advance()
    else:
        panel.chain(cpu)
        # A declared empty base hook keeps this focused on Panel's own plan.
        cpu.step_hook.previous = backend.StepHook(lambda machine: None,
            lambda machine: (backend.NEVER, False, frozenset()), lambda machine, n: None)
    try:
        record = panel.records['ADJ']
        address, mask = panel.pin(120 + record['row'])
        panel.set_key('ADJ', True)
        save(cpu, 'panel_scan', 'adj_pressed_low_row', panel)
        cpu.write(address, bytes([mask]))
        save(cpu, 'panel_scan', 'row_high_before_tick', panel)
        stop = cpu.run(8)
        save(cpu, 'panel_scan', 'row_high_after_tick', panel, stop)
        assert gpio.inputs[0xff7040b0][1] & record['column_mask']
        cpu.write(address, bytes(1))
        stop = cpu.run(8)
        save(cpu, 'panel_scan', 'row_low_after_tick', panel, stop)
        assert not gpio.inputs[0xff7040b0][1] & record['column_mask']
        for name in ('HALF', 'FULL'):
            for pressed in (True, False):
                panel.set_key(name, pressed)
                stop = cpu.run(2)
                save(cpu, 'panel_scan', name.lower() + ('_pressed' if pressed else '_released'), panel, stop)
        panel.set_key('ADJ', False)
        stop = cpu.run(4)
        save(cpu, 'panel_scan', 'all_released', panel, stop)
    finally:
        cpu.close()
    (directory / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'impl': impl, 'cases': len(result['cases']),
                      'snapshots': sum(map(len, result['cases'].values()))}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=IMPLS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    records = {}
    for impl in IMPLS:
        process = subprocess.run([sys.executable, '-I', '-B', __file__, '--worker', impl], cwd=ROOT,
                                 timeout=1800, capture_output=True, text=True)
        print(process.stdout, end='', flush=True)
        if process.returncode:
            print(process.stderr, end='', flush=True)
            raise SystemExit(process.returncode)
        records[impl] = json.loads((HERE / 'local/device-cases' / impl / 'results.json').read_text())
    differences, comparisons = [], []
    for case, points in records['step']['cases'].items():
        for index, point in enumerate(points):
            states = {}
            for impl in IMPLS:
                row = records[impl]['cases'][case][index]
                assert row['label'] == point['label']
                states[impl] = pickle.loads((ROOT / row['snapshot']).read_bytes())
            equal = states['step'] == states['copy-step'] == states['batch']
            row = {'case': case, 'label': point['label'], 'equal': equal,
                   'hashes': {impl: records[impl]['cases'][case][index]['state_hash'] for impl in IMPLS}}
            comparisons.append(row)
            if not equal:
                differences.append(row)
    result = {'comparisons': comparisons, 'differences': differences, 'passed': not differences}
    (HERE / 'local/device-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparisons': len(comparisons), 'differences': len(differences)}), flush=True)
    raise SystemExit(bool(differences))


if __name__ == '__main__':
    main()
