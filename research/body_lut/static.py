"""Bounded M32R static evidence, checked against the official ilaunch3 bytes."""
import bisect
import csv
import pickle
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, LOCAL, guard, inp, sha, dump


def index():
    cache = LOCAL/'static_index.pkl'
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    firmware = inp('artifacts/firmware/gxr-1.51/ilaunch3')
    assert sha(firmware) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    raw = firmware.read_bytes()
    segs = list(csv.DictReader(inp('research/tooling_m32r/sections/ilaunch3-sections.csv').open()))
    rows = []
    for p in sorted((ROOT/'research/tooling_m32r/disasm').glob('ilaunch3-sec*.txt')):
        inp(p)
        for line_no, line in enumerate(p.read_text().splitlines(), 1):
            m = re.match(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2} ){2,4})\s*(.*)', line)
            if not m:
                continue
            a, b, op = int(m[1], 16), bytes.fromhex(m[2]), m[3]
            seg = next((s for s in segs if int(s['load_address']) <= a <
                        int(s['load_address'])+int(s['initialized_size'])), None)
            if seg:
                off = int(seg['file_offset']) + a-int(seg['load_address'])
                assert raw[off:off+len(b)] == b, (p, hex(a))
                rows.append((a, op, str(p.relative_to(ROOT)), line_no))
    rows.sort()
    cache.write_bytes(pickle.dumps(rows, protocol=5))
    return rows


def calls(rows):
    regs, out = {}, []
    for a, op, file, line in rows:
        for s in re.split(r' -> | \|\| ', op):
            m = re.fullmatch(r'seth (r\d+|sp|fp),#0x([0-9a-f]+)', s)
            if m:
                regs[m[1]] = int(m[2], 16) << 16
                continue
            m = re.fullmatch(r'(ldi|ld24) (r\d+|sp|fp),#?(-?0x[0-9a-f]+|-?\d+)', s)
            if m:
                regs[m[2]] = int(m[3], 0) & 0xffffffff
                continue
            m = re.fullmatch(r'(or3|add3) (r\d+|sp|fp),(r\d+|sp|fp),#(-?0x[0-9a-f]+|-?\d+)', s)
            if m:
                x, y = regs.get(m[3]), int(m[4], 0)
                if x is not None:
                    regs[m[2]] = (x | y) if m[1] == 'or3' else (x+y)&0xffffffff
                else:
                    regs.pop(m[2], None)
                continue
            m = re.fullmatch(r'(bl|jl) (0x[0-9a-f]+|r\d+)', s)
            if m:
                target = int(m[2], 16) if m[1] == 'bl' else regs.get(m[2])
                out.append({'address': a, 'target': target, 'args':
                            {r:regs[r] for r in ('r4','r5','r6','r7') if r in regs},
                            'file': file, 'line': line})
                for r in ('r0','r1','r2','r3','r4','r5','r6','r7'):
                    regs.pop(r, None)
                continue
            if s.startswith(('b','jmp ')):
                regs.clear()
                continue
            m = re.match(r'(?:mv|add|sub|mul|and|or|xor|not|ld(?:ub|uh|b|h)?|pop|sll3|sra3|srl3|slli|srli|srai|addi) (r\d+|sp|fp)', s)
            if m:
                regs.pop(m[1], None)
    return out


if __name__ == '__main__':
    guard()
    rows = index()
    cc = calls(rows)
    dump('static_calls.json', cc)
    mode = sys.argv[1]
    if mode == 'window':
        a, b = [int(x, 16) for x in sys.argv[2:4]]
        selected = [r for r in rows if a <= r[0] < b]
        p = LOCAL / f'static/{a:08x}-{b:08x}.asm.txt'
        p.parent.mkdir(exist_ok=True)
        p.write_text('\n'.join(f'{r[0]:08x}: {r[1]} ; {r[2]}:{r[3]}' for r in selected)+'\n')
        print('\n'.join(f'{r[0]:08x}: {r[1]}' for r in selected[:180]))
        print('saved', len(selected), p.relative_to(ROOT))
    elif mode == 'calls':
        a, b = [int(x, 16) for x in sys.argv[2:4]]
        for c in cc:
            if a <= c['address'] < b:
                print(hex(c['address']), hex(c['target']) if c['target'] else 'indirect',
                      {k:hex(v) for k,v in c['args'].items()})
    elif mode == 'refs':
        t = int(sys.argv[2], 16)
        for c in cc:
            if c['target'] == t:
                print(hex(c['address']), c['file'], c['line'])
    elif mode == 'find':
        pat = re.compile(sys.argv[2])
        hits = [r for r in rows if pat.search(r[1])]
        dump('static_find.json', hits)
        for r in hits[:100]:
            print(hex(r[0]), r[1])
        print('hits', len(hits))
    dump('static_identity.json', {'isa': 'M32R big-endian mixed 16/32-bit',
        'instruction_rows_checked_against_official': len(rows),
        'ilaunch3_sha256': sha(inp('artifacts/firmware/gxr-1.51/ilaunch3')),
        'call_index_is_heuristic': True})
