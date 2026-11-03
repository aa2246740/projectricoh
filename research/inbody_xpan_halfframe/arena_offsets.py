#!/usr/bin/python3 -I -B
"""Read-only, linear (not interprocedural) scan: for each read of the image
arena start word 0x200C0DD0 in ilaunch3, collect large constants built in
the next 24 instructions (ld24 / seth+or3) and whether the arena size word
0x200C0DD4 is read nearby.  The largest constant per site approximates the
deepest fixed offset a layout uses from the arena start.  Candidates only.
stdout: one line per site, then a summary."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'research/tooling_m32r/disasm'
ARENA = 0x076C0000
CARVE = 0x00C00000

rows = []
for f in sorted(D.glob('ilaunch3-sec*.disasm.txt')):
    lines = f.read_text(errors='replace').splitlines()
    for i, ln in enumerate(lines):
        if 'or3' in ln and ('#0xdd0' in ln) and i and '#0x200c' in lines[i - 1]:
            win = lines[max(0, i - 24):i + 24]
            size_read = any('#0xdd4' in w for w in win)
            consts = []
            hi = {}
            for w in lines[i:i + 24]:
                m = re.search(r'ld24 r(\d+),0x([0-9a-f]+)', w)
                if m:
                    consts.append(int(m.group(2), 16))
                m = re.search(r'seth r(\d+),#0x([0-9a-f]+)', w)
                if m:
                    hi[m.group(1)] = int(m.group(2), 16)
                m = re.search(r'or3 r(\d+),r(\d+),#0x([0-9a-f]+)', w)
                if m and m.group(2) in hi and hi[m.group(2)] < 0x2000:
                    consts.append(hi[m.group(2)] << 16 | int(m.group(3), 16))
            big = max(consts) if consts else 0
            rows.append((ln.split(':')[0], size_read, big))

over = [r for r in rows if r[2] >= ARENA - CARVE]
for a, s, b in rows:
    flag = ' >=new_size' if b >= ARENA - CARVE else ''
    print(f'{a} size_read={int(s)} max_const={b:#x}{flag}')
print(f'# sites {len(rows)}, with size word nearby {sum(r[1] for r in rows)}, '
      f'fixed constant >= arena-12MiB ({ARENA - CARVE:#x}): {len(over)}')
