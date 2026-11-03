"""Bounded constant/call candidates; each instruction is checked against the archive."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
from static import Image
import re

LINE = re.compile(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2} ){1,4})\s*(.*)$')
REG = r'(r\d+|fp|lr|sp)'
NUM = r'(-?0x[0-9a-f]+|-?\d+)'

def instructions(name):
    for p in sorted((r.LOCAL / 'disasm').glob(name + '-segment*.asm')):
        with p.open() as src:
            for no, line in enumerate(src, 1):
                match = LINE.match(line)
                if match:
                    yield p.name, no, int(match[1], 16), bytes.fromhex(match[2]), match[3]

def build(name):
    im = Image(name)
    refs, calls, accesses = [], [], []
    regs, count = {}, 0
    last_file = None
    for source, line, pc, raw, code in instructions(name):
        assert im.read(pc, len(raw)) == raw
        count += 1
        if source != last_file:
            regs.clear()
            last_file = source
        for op in re.split(r'\s*(?:\|\||->)\s*', code):
            op = op.strip()
            meta = dict(pc=pc, file_offset=im.offset(pc), source=source, line=line, op=op)
            mem = re.search(r'@\((-?\d+),' + REG + r'\)|@(\+?)' + REG + r'(\+?)', op)
            if mem:
                if mem[2]:
                    base, disp = mem[2], int(mem[1])
                else:
                    base, disp = mem[4], 4 if mem[3] else 0
                if base in regs:
                    accesses.append(dict(meta, address=(regs[base] + disp) & 0xffffffff))
            dest, value = None, None
            q = re.fullmatch(r'(ldi|ld24|seth) ' + REG + ',#?' + NUM, op)
            if q:
                dest, value = q[2], int(q[3], 0)
                if q[1] == 'seth':
                    value <<= 16
            else:
                q = re.fullmatch(r'(or3|add3|and3) ' + REG + ',' + REG + ',#' + NUM, op)
                if q:
                    dest, old, k = q[2], regs.get(q[3]), int(q[4], 0)
                    if old is not None:
                        value = old | k if q[1] == 'or3' else old + k if q[1] == 'add3' else old & k
                else:
                    q = re.fullmatch(r'mv ' + REG + ',' + REG, op)
                    if q:
                        dest, value = q[1], regs.get(q[2])
                    else:
                        q = re.fullmatch(r'(addi|slli|srli|srai) ' + REG + ',#' + NUM, op)
                        if q:
                            dest, old, k = q[2], regs.get(q[2]), int(q[3], 0)
                            if old is not None:
                                value = old + k if q[1] == 'addi' else old << (k & 31) if q[1] == 'slli' else old >> (k & 31)
            if dest:
                regs.pop(dest, None)
                if value is not None:
                    regs[dest] = value & 0xffffffff
                    refs.append(dict(meta, value=regs[dest], register=dest))
                continue
            q = re.fullmatch(r'(add|sub|or|and) ' + REG + ',' + REG, op)
            if q:
                dest, left, right = q[2], regs.get(q[2]), regs.get(q[3])
                regs.pop(dest, None)
                if left is not None and right is not None:
                    value = left + right if q[1] == 'add' else left - right if q[1] == 'sub' else left | right if q[1] == 'or' else left & right
                    regs[dest] = value & 0xffffffff
                    refs.append(dict(meta, value=regs[dest], register=dest))
                continue
            q = re.fullmatch(r'jl ' + REG, op)
            direct = re.fullmatch(r'bl (0x[0-9a-f]+)', op)
            if q or direct:
                target = regs.get(q[1]) if q else int(direct[1], 16)
                if target is not None:
                    calls.append(dict(meta, target=target, args={k:regs[k] for k in ('r4', 'r5', 'r6', 'r7') if k in regs}))
                for reg in [f'r{i}' for i in range(8)] + ['lr']:
                    regs.pop(reg, None)
                continue
            q = re.match(r'(?:ld\w*|pop|neg|mul\w*|xor\w*|not|add|sub|or|and) ' + REG, op)
            if q:
                regs.pop(q[1], None)
            if op.startswith(('jmp ', 'bra ', 'rte')):
                regs.clear()
    r.dump(r.LOCAL / (name + '-index.json'), dict(image=name, byte_checked=count,
        limit='Linear candidates only, including possible embedded data. Conditional CFG and aliases are not closed; inspect concrete windows.',
        refs=refs, calls=calls, accesses=accesses))
    print(name, count, 'byte-checked instructions;', len(calls), 'call candidates')

def query(name, kind, low, high=None):
    entries = r.json.loads((r.LOCAL / (name + '-index.json')).read_text())[kind]
    key = dict(refs='value', calls='target', accesses='address')[kind]
    lo, hi = int(low, 0), int(high, 0) if high is not None else int(low, 0) + 1
    hits = [row for row in entries if lo <= row[key] < hi]
    for row in hits:
        print(r.json.dumps({k:hex(v) if isinstance(v, int) and k not in ('line',) else v for k,v in row.items()}))
    print('hits', len(hits))

if __name__ == '__main__':
    if sys.argv[1] == 'build':
        build(sys.argv[2])
    else:
        query(*sys.argv[1:])
    r.finish('index_' + sys.argv[1])
