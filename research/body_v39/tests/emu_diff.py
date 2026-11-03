#!/usr/bin/python3
"""Lockstep comparison of official 1.51, v3.8 and v3.9 MAIN in the batch emulator.

Same cold schedule as emu_boot.py, but the three machines advance phase by phase
in one process and every phase compares the full 8 MiB RAM image. Differing bytes
are classified: the resident window and root page; the nine replaced hook words;
the task stack pool [0x2042C200,0x204A9200); everything else. Observations at the
probe points are compared without step counts (v3.9 executes extra trampoline
instructions at H09/H10, so equal step budgets end at slightly different points).

  TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 \
  nice -n 10 /usr/bin/python3 -I -B research/body_v39/tests/emu_diff.py
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emu_boot as E  # noqa: E402  (same schedule, image table and key helper)

WINDOW = (0x2005276C, 0x20054800)
STACKS = (0x2042C200, 0x204A9200)
HOOKS = [(0x2028709C, 8), (0x202870A8, 4), (0x201FEBE4, 8), (0x202BE24C, 4), (0x202871D8, 4),
         (0x202BB968, 4), (0x2017098C, 4), (0x202B120C, 4), (0x2015F9D8, 4)]


def classify(a, b):
    total = dict(window=0, hook_words=0, stack_pool=0, other=0)
    other = []
    i, n = 0, len(a)
    while i < n:
        if a[i] == b[i]:
            i += 1
            continue
        j = i
        while j < n and a[j] != b[j]:
            j += 1
        start, end = 0x20000000 + i, 0x20000000 + j
        if WINDOW[0] <= start and end <= WINDOW[1]:
            total['window'] += j - i
        elif any(h <= start and end <= h + k for h, k in HOOKS):
            total['hook_words'] += j - i
        elif STACKS[0] <= start and end <= STACKS[1]:
            total['stack_pool'] += j - i
        else:
            total['other'] += j - i
            if len(other) < 40:
                other.append([hex(start), hex(end)])
        i = j
    total['other_ranges'] = other
    return total


class Runner:
    def __init__(self, name):
        import struct
        self.name = name
        path, expected = E.IMAGES[name]
        raw = path.read_bytes()
        if expected:
            assert hashlib.sha256(raw).hexdigest() == expected
        self.machine = E.Machine()
        cpu = self.cpu = self.machine.cpu
        for row in self.machine.image.sections:
            off, n = row['file_offset'], row['initialized_size']
            cpu.write(row['load_address'], raw[off:off + n])
        cpu.set_mode('fast')
        cpu.set_batch(True)
        self.panel = E.Panel(cpu, self.machine.devices)
        E.add_matrix_keys(self.panel, cpu)
        self.panel.chain(cpu)
        serial = self.machine.devices['serial']
        mask, level = serial.input_bytes.get(0, (0, 0))
        serial.input_bytes[0] = (mask | 2, level & ~2)
        E.set_dial(cpu, self.machine.devices, 2)
        self.rows, self.phase = [], 'cold'
        for address, label in E.POINTS.items():
            old = cpu.breakpoints.get(address)
            def hit(current, label=label, old=old):
                first = old(current) if old else False
                self.rows.append((label, self.phase, self.machine.task(), current.get_reg('r11'),
                                  int.from_bytes(cpu.read(0x205D9C00, 4), 'big')))
                return first
            cpu.add_breakpoint(address, hit)

    def step(self, phase, key, pressed, budget):
        self.phase = phase
        if key:
            self.panel.set_key(key, pressed)
        result = self.cpu.run(budget)
        return result.reason

    def ram(self):
        return bytes(self.cpu.read(0x20000000, 0x800000))

    def close(self):
        self.machine.close()


def main():
    signal.alarm(2400)
    cold, press, release = 55_000_000, 400_000, 700_000
    runners = {n: Runner(n) for n in E.IMAGES}
    schedule = [('cold', None, None, cold)]
    for key in E.KEYS.split(','):
        schedule += [(key + '-down', key, True, press), (key + '-up', key, False, release)]
    phases, start = [], time.monotonic()
    try:
        for label, key, pressed, budget in schedule:
            stops = {n: r.step(label, key, pressed, budget) for n, r in runners.items()}
            ram = {n: r.ram() for n, r in runners.items()}
            row = dict(phase=label, stops=stops,
                       state={n: int.from_bytes(ram[n][0x5D9C00:0x5D9C04], 'big') for n in ram},
                       task={n: r.machine.task() for n, r in runners.items()},
                       v38_vs_v39=classify(ram['v38'], ram['v39']),
                       official_vs_v39=classify(ram['official'], ram['v39']),
                       official_vs_v38=classify(ram['official'], ram['v38']),
                       seconds=round(time.monotonic() - start, 1))
            phases.append(row)
            print(json.dumps({k: row[k] for k in ('phase', 'state', 'seconds')} |
                             {'v38_vs_v39_other': row['v38_vs_v39']['other'],
                              'official_vs_v39_other': row['official_vs_v39']['other']}), flush=True)
        obs = {n: r.rows for n, r in runners.items()}
        out = dict(classification='offline_model_observation', cold_origin=True, no_card=True, synthetic_unit=True,
                   schedule=dict(cold=cold, press=press, release=release, keys=E.KEYS),
                   images={n: hashlib.sha256(E.IMAGES[n][0].read_bytes()).hexdigest() for n in E.IMAGES},
                   observations_equal=dict(v38_vs_v39=obs['v38'] == obs['v39'],
                                           official_vs_v39=obs['official'] == obs['v39']),
                   observation_counts={n: len(v) for n, v in obs.items()},
                   observations_v39=obs['v39'],
                   root_page_v39=bytes(runners['v39'].cpu.read(0x20054700, 256)).hex(),
                   phases=phases,
                   script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (HERE.parent / 'evidence/emu-diff.json').write_text(json.dumps(out, indent=1) + '\n')
        print(json.dumps(out['observations_equal']))
    finally:
        for r in runners.values():
            r.close()
        signal.alarm(0)


if __name__ == '__main__':
    main()
