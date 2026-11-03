#!/usr/bin/python3
"""Observe original MAIN startup and GPIO events without changing source files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-plan')
assert Path(os.environ['TMPDIR']).resolve() == TEMP
sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
from storage_run import Machine
from panel import Panel
from dial import set_dial


def main():
    signal.alarm(600)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='boot-observations')
    parser.add_argument('--cold-budget', type=int, default=55_000_000)
    parser.add_argument('--skip-keys', action='store_true')
    args = parser.parse_args()
    if not args.name.replace('-', '').isalnum():
        raise ValueError('Use a simple evidence name')
    destination = HERE / 'local'
    destination.mkdir(exist_ok=True)
    target = destination / (args.name + '.json')
    if target.exists():
        raise RuntimeError('Use a separate evidence name for another run')
    machine = Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    cpu.set_batch(True)
    panel = Panel(cpu, machine.devices)
    panel.chain(cpu)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    dial = set_dial(cpu, machine.devices, 2)
    rows = []
    counts = {}
    phase = 'cold'

    def word(address):
        return int.from_bytes(cpu.read(address, 4), 'big')

    def half(address):
        return int.from_bytes(cpu.read(address, 2), 'big')

    def byte(address):
        return cpu.read(address, 1)[0]

    def mark(address, name):
        def hit(current):
            counts[name] = counts.get(name, 0) + 1
            if len(rows) < 256:
                task = machine.task()
                record = 0x2042bfe4 + 12 * task if 1 <= task <= 44 else 0
                rows.append(dict(
                    name=name, phase=phase, step=current.steps,
                    task=task, pc=hex(address), event=hex(current.get_reg('r11')),
                    state=word(0x205d9c00), layer=byte(0x205a280f),
                    activity=word(0x205d9bf8), psw=hex(current.get_reg('psw')),
                    sp=hex(current.get_reg('r15')), lr=hex(current.get_reg('lr')),
                    stack_record=[word(record + 4 * i) for i in range(3)] if record else [],
                    settings_address=hex(word(0x200c0dac)),
                    settings_bytes=word(0x200c0db0),
                ))
            return False
        return hit

    points = {
        0x202b1100: 'ui-loop', 0x202b120c: 'ui-event',
        0x20174f90: 'queue13-loop', 0x2015f9d8: 'main-encode-call',
        0x2036e9ac: 'update-selection', 0x2036e34c: 'update-handler',
        0x2017098c: 'capture-sender',
    }
    for address, name in points.items():
        old = cpu.breakpoints.get(address)
        observe = mark(address, name)
        def combined(current, old=old, observe=observe):
            first = old(current) if old else False
            return observe(current) or first
        cpu.add_breakpoint(address, combined)
    started = time.monotonic()
    segments = []
    try:
        schedule = [('cold', None, None, args.cold_budget),
                    ('ok-down', 'OK', True, 1_000_000),
                    ('ok-up', 'OK', False, 1_000_000),
                    ('adj-down', 'ADJ', True, 1_000_000),
                    ('adj-up', 'ADJ', False, 1_000_000)]
        if args.skip_keys:
            schedule = schedule[:1]
        for phase, key, pressed, budget in schedule:
            if key:
                panel.set_key(key, pressed)
            start = cpu.steps
            result = cpu.run(budget)
            segments.append(dict(phase=phase, start_step=start,
                                 end_step=cpu.steps, stop=result.to_dict(),
                                 state=word(0x205d9c00), layer=byte(0x205a280f)))
            print(json.dumps(segments[-1]), flush=True)
            if result.reason != 'max_steps':
                break
        result = dict(
            classification='offline_model_observation',
            image_sha256=machine.image.sha256,
            library_sha256=hashlib.sha256((ROOT / 'tools/gxr_emulator_batch/build/libgxr_m32r.dylib').read_bytes()).hexdigest(),
            cold_origin=True, no_card=True, synthetic_unit=True,
            elapsed_seconds=round(time.monotonic()-started, 3),
            counts=counts, observations=rows, segments=segments,
            panel_events=panel.events, dial=dial,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            native_stack_records={str(task):dict(address=hex(0x2042bfe4+12*task),
                words=[word(0x2042bfe4+12*task+4*i) for i in range(3)]) for task in (6,26)},
            final=dict(task=machine.task(), pc=hex(cpu.get_reg('pc')),
                       state=word(0x205d9c00), layer=byte(0x205a280f)),
            task_entries={str(key):hex(value) for key,value in machine.observer.task_entries.items()},
            queue_waits=machine.observer.queue_waits,
            sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((ROOT / 'tools/gxr_emulator_batch').glob('*.py'))},
        )
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({key:result[key] for key in ['elapsed_seconds','counts','final']}, ensure_ascii=False), flush=True)
    finally:
        machine.close()
        signal.alarm(0)


if __name__ == '__main__':
    main()
