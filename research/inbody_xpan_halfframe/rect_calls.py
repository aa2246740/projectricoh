#!/usr/bin/python3 -I -B
"""Read-only: list call sites of the body OSD rect-fill primitive
(ilaunch3 0x201D709C, args r4=context, r5=&{x,y,w,h} u16, r6=colour index)
and summarise the immediates set up in the 28 instructions before each call
(screen-size constants and colour index). stdout only."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'research/tooling_m32r/disasm'
TARGET = sys.argv[1] if len(sys.argv) > 1 else '0x709c'
HI = sys.argv[2] if len(sys.argv) > 2 else '0x201d'
INTEREST = {'480', '640', '360', '424', '426', '427', '213', '214', '160', '320', '120', '240', '107', '106'}

for f in sorted(D.glob('ilaunch3-sec0[6-9]*.disasm.txt')):
    lines = f.read_text(errors='replace').splitlines()
    for i, ln in enumerate(lines):
        if f'#{TARGET}' in ln and 'or3' in ln and i and f'#{HI}' in lines[i - 1]:
            win = lines[max(0, i - 28):i + 3]
            imms = []
            colour = None
            for w in win:
                m = re.search(r'ldi r(\d+),#(-?\d+)', w)
                if m:
                    imms.append(m.group(2))
                    if m.group(1) == '6':
                        colour = m.group(2)
            hit = sorted(set(imms) & INTEREST)
            addr = ln.split(':')[0]
            print(f'{addr} colour={colour} sizes={",".join(hit)} imms={",".join(imms[-10:])}')
