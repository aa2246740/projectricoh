#!/usr/bin/python3
"""Values behind the RAM differences found by emu_diff.py (outside the resident
window, hook words and the task stack pool) after the cold phase, for official,
v3.8 and v3.9. Also runs v3.8 for extra steps to see whether the v3.9 values are
reached later (step-timing skew) rather than being different state.

  TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39 \
  nice -n 10 /usr/bin/python3 -I -B research/body_v39/tests/emu_words.py
"""
import json
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from emu_diff import Runner, classify  # noqa: E402


def main():
    signal.alarm(2400)
    diff = json.loads((HERE.parent / 'evidence/emu-diff.json').read_text())
    ranges = diff['phases'][0]['v38_vs_v39']['other_ranges'] + diff['phases'][0]['official_vs_v39']['other_ranges']
    words = sorted({int(a, 16) & ~3 for a, _ in ranges})
    cold = 55_000_000
    runners = {n: Runner(n) for n in ('official', 'v38', 'v39')}
    try:
        for r in runners.values():
            r.step('cold', None, None, cold)
        def read(r):
            return {hex(w): r.cpu.read(w, 4).hex() for w in words}
        values = {n: read(r) for n, r in runners.items()}
        steps = {n: r.cpu.steps for n, r in runners.items()}
        ram39 = runners['v39'].ram()
        # step the v3.8 machine forward in small slices and look for the v3.9 values
        later = []
        for k in range(1, 41):
            runners['v38'].step('extra', None, None, 5000)
            now = read(runners['v38'])
            same = sum(now[w] == values['v39'][w] for w in now)
            later.append(dict(extra_steps=5000 * k, words_equal_to_v39=same,
                              other_bytes=classify(runners['v38'].ram(), ram39)['other']))
        out = dict(words=[hex(w) for w in words], values=values, steps=steps, v38_extra=later)
        (HERE.parent / 'evidence/emu-words.json').write_text(json.dumps(out, indent=1) + '\n')
        best = min(later, key=lambda x: x['other_bytes'])
        print(json.dumps(dict(words=len(words), best=best)))
    finally:
        for r in runners.values():
            r.close()
        signal.alarm(0)


if __name__ == '__main__':
    main()
