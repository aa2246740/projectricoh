"""Track constants and S-relative references inside straight-line code only."""
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect


def parse(text):
    for index, op in enumerate(re.split(r' -> | \|\| ', text)):
        name, _, tail = op.partition(' ')
        args = re.findall(r'@\([^)]*\)|[^,]+', tail)
        yield index, name, args, op


def immediate(value):
    value = value.lstrip('#')
    return int(value, 0)


def main():
    collect.preflight()
    im = collect.Image()
    calls, fields, constants, outgoing = [], [], [], []
    verified = 0
    regs = {}
    for address, raw, text, source, line in im.instructions():
        verified += len(raw)
        for index, name, args, op in parse(text):
            pc = address+2*index
            d = args[0] if args else ''
            row = dict(address=hex(pc), op=op, source=source, line=line)
            if name in ('jl', 'bl'):
                target = regs.get(d) if name == 'jl' else immediate(d)
                if isinstance(target, int):
                    row['target'] = hex(target)
                    row['args'] = {r: (hex(v) if isinstance(v, int) else f'S+{v[1]:#x}')
                        for r in ('r4', 'r5', 'r6', 'r7') if (v := regs.get(r)) is not None}
                    calls.append(row)
                    if any(isinstance(regs.get(r), tuple) for r in ('r4', 'r5', 'r6', 'r7')):
                        outgoing.append(row)
            effective = None
            if name in ('ld', 'ldh', 'lduh', 'ldb', 'ldub', 'st', 'sth', 'stb') and len(args) > 1:
                mem = args[1]
                mm = re.fullmatch(r'@\((-?\d+),(\w+)\)', mem)
                base = mm[2] if mm else mem.removeprefix('@').rstrip('+')
                delta = int(mm[1]) if mm else 0
                value = regs.get(base)
                if isinstance(value, tuple):
                    effective = ('S', value[1]+delta)
                    row['offset'] = hex(effective[1])
                    row['width'] = 4 if name in ('ld', 'st') else 2 if name in ('ldh', 'lduh', 'sth') else 1
                    row['kind'] = 'write' if name.startswith('st') else 'read'
                    fields.append(row)
                elif isinstance(value, int):
                    effective = (value+delta) & 0xffffffff
                    if 0x200c0d90 <= effective < 0x200c0df4:
                        constants.append(dict(row, target=hex(effective)))
            try:
                if name == 'seth':
                    regs[d] = immediate(args[1]) << 16
                elif name in ('ldi', 'ld24'):
                    regs[d] = immediate(args[1]) & 0xffffffff
                elif name == 'mv':
                    if args[1] in regs:
                        regs[d] = regs[args[1]]
                    else:
                        regs.pop(d, None)
                elif name == 'ld' and effective == 0x200c0dac:
                    regs[d] = ('S', 0)
                elif name in ('or3', 'add3', 'and3') and args[1] in regs:
                    x, y = regs[args[1]], immediate(args[2])
                    if name == 'add3' and 0x8000 <= y <= 0xffff:
                        y -= 65536
                    if isinstance(x, tuple) and name == 'add3':
                        regs[d] = ('S', x[1]+y)
                    elif isinstance(x, int):
                        regs[d] = (x | y if name == 'or3' else x+y if name == 'add3' else x & y) & 0xffffffff
                    else:
                        regs.pop(d, None)
                elif name in ('addi', 'slli', 'srli') and d in regs:
                    x, y = regs[d], immediate(args[1])
                    if isinstance(x, tuple) and name == 'addi':
                        regs[d] = ('S', x[1]+y)
                    elif isinstance(x, int):
                        regs[d] = (x+y if name == 'addi' else x << y if name == 'slli' else x >> y) & 0xffffffff
                    else:
                        regs.pop(d, None)
                elif name == 'add' and d in regs and args[1] in regs:
                    x, y = regs[d], regs[args[1]]
                    if isinstance(x, tuple) and isinstance(y, int):
                        regs[d] = ('S', x[1]+y)
                    elif isinstance(x, int) and isinstance(y, tuple):
                        regs[d] = ('S', y[1]+x)
                    elif isinstance(x, int) and isinstance(y, int):
                        regs[d] = (x+y) & 0xffffffff
                    else:
                        regs.pop(d, None)
                elif name in ('jl', 'bl'):
                    for r in range(8):
                        regs.pop('r'+str(r), None)
                elif name.startswith('b') or name in ('jmp', 'rte'):
                    regs.clear()
                elif name not in ('nop', 'cmp', 'cmpu', 'cmpi', 'cmpui', 'cmpeq', 'st', 'sth', 'stb', 'push'):
                    regs.pop(d, None)
            except (ValueError, IndexError):
                regs.clear()
    collect.save('calls.json', calls)
    collect.save('s-fields.json', fields)
    collect.save('s-operations.json', outgoing)
    collect.save('parameter-pointers.json', constants)
    occupied = {n for row in fields for n in range(int(row['offset'], 16), int(row['offset'], 16)+row['width'])}
    gaps, start = [], None
    for n in range(4093):
        if n < 4092 and n not in occupied:
            if start is None:
                start = n
        elif start is not None:
            if n-start >= 16:
                gaps.append(dict(start=hex(start), end=hex(n), size=n-start))
            start = None
    summary = dict(verified_bytes=verified, calls=len(calls), fields=len(fields),
                   direct_bytes=len(occupied), gaps=gaps,
                   source_sha256=collect.sha(HERE/'scan.py'),
                   original_sha256=collect.EXPECTED,
                   limits='Syntactic candidates only; aliases, indexed ranges and indirect calls remain open.')
    collect.save('scan-summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
