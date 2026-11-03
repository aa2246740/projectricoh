#!/usr/bin/python3
"""Whole-body cold boot in the batch emulator: official 1.51, v3.8 and v3.9 MAIN.

Each image runs the same schedule from the same cold state (no card, synthetic
unit, dial 2): a cold boot budget, then key presses through the GPIO model (as
research/body_next_steps/tools/observe_keys.py). The emulator Machine is built
from the official image (its NAND fixture is bound to that identity); the 16
loaded sections are then overwritten from the image under test before the
first instruction (section headers are identical in all three files).

Compared per phase: the full 8 MiB RAM image outside the resident window
[0x2005276C,0x20054800) and the root/pins page, CPU registers, the task id, and
the observation records at H10 (0x202B120C), the 2F02 sender (H09 site), the
encoder call (H40 site), update selection/handler and the key message entry.

  TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 \
  nice -n 10 /usr/bin/python3 -I -B research/body_v39/tests/emu_boot.py
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39')
assert Path(os.environ['TMPDIR']).resolve() == TEMP
sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
from storage_run import Machine  # noqa: E402
from panel import Panel  # noqa: E402
from dial import set_dial  # noqa: E402

# Copied from research/body_next_steps/tools/observe_keys.py (matrix keys the
# stock Panel class does not name; raw code -> label).
EXTRA = {19: 'RAW19', 20: 'RAW20', 22: 'RAW22', 26: 'RAW26', 27: 'RAW27',
         32: 'RAW32', 51: 'RAW51', 52: 'RAW52', 53: 'RAW53', 58: 'RAW58',
         59: 'RAW59', 60: 'RAW60', 61: 'RAW61'}


def add_matrix_keys(panel, cpu):
    image = cpu.image
    def official(address, size):
        off = image.offset(address, size)
        return image.raw[off:off+size]
    codes = struct.unpack('>72I', official(0x200C5E78, 72*4))
    for code, name in EXTRA.items():
        index = codes.index(code)
        words = struct.unpack('>10I', official(0x200C5338+40*index, 40))
        assert 32 <= index < 52, (code, index)
        panel.records[name] = {'index': index, 'code': code, 'active': words[6],
                               'pin': words[2], 'kind': words[1],
                               'row': (index-32)//5, 'column_mask': words[3] >> 24}

IMAGES = {
    'official': (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3', 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'),
    'v38': (ROOT / 'firmware/resident_v38/local/body/ilaunch3', 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'),
    'v39': (ROOT / 'firmware/image_v39/local/ilaunch3', None),
}
WINDOW = (0x2005276C, 0x20054800)
KEYS = 'OK,ADJ,DISP,UP,DOWN,LEFT,RIGHT,RAW19,RAW20,RAW22,RAW26,RAW27,HALF'
POINTS = {0x202B120C: 'ui-event', 0x2017098C: 'capture-sender', 0x2015F9D8: 'main-encode-call',
          0x2036E9AC: 'update-selection', 0x2036E34C: 'update-handler', 0x202AFE98: 'key-message'}


def run_image(name, cold, press, release):
    path, expected = IMAGES[name]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected:
        assert digest == expected, name
    machine = Machine()
    cpu = machine.cpu
    for row in machine.image.sections:                        # overwrite with the image under test
        off, n = row['file_offset'], row['initialized_size']
        assert struct.unpack_from('>5I', raw, 0x20 + 20 * row['index'])[0] + 0x200 == off
        cpu.write(row['load_address'], raw[off:off + n])
    assert cpu.get_reg('pc') == struct.unpack_from('>I', raw, 0x160)[0]
    cpu.set_mode('fast')
    cpu.set_batch(True)
    panel = Panel(cpu, machine.devices)
    add_matrix_keys(panel, cpu)
    panel.chain(cpu)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    set_dial(cpu, machine.devices, 2)
    rows = []

    def word(a):
        return int.from_bytes(cpu.read(a, 4), 'big')

    def mark(address, label):
        def hit(current):
            rows.append(dict(name=label, phase=phase[0], step=current.steps, task=machine.task(),
                             r11=current.get_reg('r11'), state=word(0x205D9C00), layer=cpu.read(0x205A280F, 1)[0],
                             sp=hex(current.get_reg('r15')), lr=hex(current.get_reg('lr'))))
            return False
        return hit
    phase = ['cold']
    for address, label in POINTS.items():
        old = cpu.breakpoints.get(address)
        observe = mark(address, label)
        def combined(current, old=old, observe=observe):
            first = old(current) if old else False
            return observe(current) or first
        cpu.add_breakpoint(address, combined)
    schedule = [('cold', None, None, cold)]
    for key in KEYS.split(','):
        schedule += [(key + '-down', key, True, press), (key + '-up', key, False, release)]
    phases, start = [], time.monotonic()
    try:
        for label, key, pressed, budget in schedule:
            phase[0] = label
            if key:
                panel.set_key(key, pressed)
            result = cpu.run(budget)
            ram = bytes(cpu.read(0x20000000, 0x800000))
            outside = ram[:WINDOW[0] - 0x20000000] + ram[WINDOW[1] - 0x20000000:]
            phases.append(dict(phase=label, steps=cpu.steps, stop=result.reason, task=machine.task(),
                               pc=hex(cpu.get_reg('pc')), regs=[cpu.get_reg(f'r{i}') for i in range(16)],
                               state=word(0x205D9C00), ram_outside_window=hashlib.sha256(outside).hexdigest(),
                               root_page=hashlib.sha256(ram[0x54700:0x54800]).hexdigest(),
                               seconds=round(time.monotonic() - start, 1)))
            print(json.dumps(dict(image=name, **{k: phases[-1][k] for k in ('phase', 'steps', 'stop', 'state', 'seconds')})), flush=True)
            if result.reason != 'max_steps':
                break
        return dict(image=name, sha256=digest, phases=phases, observations=rows,
                    final_root_bytes=bytes(cpu.read(0x20054700, 256)).hex())
    finally:
        machine.close()


def main():
    signal.alarm(2400)
    cold, press, release = 55_000_000, 400_000, 700_000
    results = {name: run_image(name, cold, press, release) for name in IMAGES}
    def view(r):
        return [(o['name'], o['phase'], o['step'], o['task'], o['r11'], o['state']) for o in r['observations']]
    compare = {}
    for a, b in (('v38', 'v39'), ('official', 'v39'), ('official', 'v38')):
        pa, pb = results[a]['phases'], results[b]['phases']
        compare[f'{a}_vs_{b}'] = dict(
            phases=len(pa) == len(pb),
            ram_outside_window_equal=[x['ram_outside_window'] == y['ram_outside_window'] for x, y in zip(pa, pb)],
            regs_equal=[x['regs'] == y['regs'] and x['pc'] == y['pc'] for x, y in zip(pa, pb)],
            observations_equal=view(results[a]) == view(results[b]))
    h10 = {}
    for o in results['v39']['observations']:
        if o['name'] == 'ui-event' and o['phase'].endswith('-down'):
            h10.setdefault(o['phase'][:-5], []).append(hex(o['r11']))
    out = dict(classification='offline_model_observation', cold_origin=True, no_card=True, synthetic_unit=True,
               schedule=dict(cold=cold, press=press, release=release, keys=KEYS),
               library_sha256=hashlib.sha256((ROOT / 'tools/gxr_emulator_batch/build/libgxr_m32r.dylib').read_bytes()).hexdigest(),
               script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               images={k: v['sha256'] for k, v in results.items()}, compare=compare, h10_codes_on_press_v39=h10,
               root_after_v39=results['v39']['final_root_bytes'][:64],
               results=results)
    target = HERE.parent / 'evidence/emu-boot.json'
    target.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(json.dumps(dict(compare=compare, h10=h10)))
    signal.alarm(0)


if __name__ == '__main__':
    main()
