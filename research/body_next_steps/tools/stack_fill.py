#!/usr/bin/python3
"""Cold-boot official MAIN (no card) and summarise the byte content of the
task 6 and task 26 stacks: is unused stack pre-filled with a pattern, and
how deep has each stack been touched so far. Offline model only.

Run: TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-next-steps \
     nice -n 10 /usr/bin/python3 -I -B research/body_next_steps/tools/stack_fill.py --name stack-fill-r1
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert Path(os.environ['TMPDIR']).resolve() == Path('/Volumes/Workspace/Scratch/tmp/projectricoh/body-next-steps')
sys.path.insert(0, str(ROOT / 'tools/gxr_emulator_batch'))
from storage_run import Machine  # noqa: E402
from panel import Panel  # noqa: E402
from dial import set_dial  # noqa: E402


def main():
    signal.alarm(600)
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--budget', type=int, default=40_000_000)
    args = parser.parse_args()
    target = ROOT / 'research/body_next_steps/local/emulator' / (args.name + '.json')
    if target.exists():
        raise RuntimeError('evidence name already used')
    machine = Machine()
    cpu = machine.cpu
    cpu.set_mode('fast')
    cpu.set_batch(True)
    panel = Panel(cpu, machine.devices)
    panel.chain(cpu)
    serial = machine.devices['serial']
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    set_dial(cpu, machine.devices, 2)
    try:
        result = cpu.run(args.budget)
        out = dict(classification='offline_model_observation', cold_origin=True, no_card=True,
                   steps=cpu.steps, stop=result.to_dict(), tasks={})
        for task in (6, 26):
            record = 0x2042bfe4 + 12 * task
            words = [int.from_bytes(cpu.read(record + 4 * i, 4), 'big') for i in range(3)]
            base, size = words[1], words[2]
            data = bytes(cpu.read(base, size))
            common = Counter(data[i:i + 4] for i in range(0, size, 4)).most_common(3)
            fill = common[0][0]
            low = next((i for i in range(0, size, 4) if data[i:i + 4] != fill), size)
            # r2: list every non-fill word with its offset, so isolated words at
            # the bottom (a fixed record or guard) can be told apart from the
            # contiguous region the task has actually used from the top down.
            nonfill = [i for i in range(0, size, 4) if data[i:i + 4] != fill]
            out['tasks'][str(task)] = dict(record=hex(record), words=words, base=hex(base), size=size,
                                           common_words=[(w.hex(), n) for w, n in common],
                                           first_non_fill_offset=low,
                                           nonfill_count=len(nonfill),
                                           bottom_words=[(hex(base + i), data[i:i + 4].hex()) for i in range(0, 32, 4)],
                                           lowest_nonfill_above_64=next((hex(base + i) for i in nonfill if i >= 64), None),
                                           nonfill_offsets_below_1024=[i for i in nonfill if i < 1024],
                                           sha256=hashlib.sha256(data).hexdigest())
        target.write_text(json.dumps(out, indent=1) + '\n')
        print(json.dumps(out['tasks']))
    finally:
        machine.close()
        signal.alarm(0)


if __name__ == '__main__':
    main()
