#!/usr/bin/env python3
"""Bounded syntactic references, with constants tracked only inside basic blocks."""
from pathlib import Path
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

FIELDS = {
    0x204f41e8: 'storage_state', 0x204f41ea: 'storage_flags',
    0x204f0cc4: 'storage_message_buffer_id', 0x204c8668: 'file_count',
    0x2037f924: 'adj_control', 0x2037f730: 'ui_table_candidate',
    0x2037f734: 'ui_table_candidate', 0x2037f738: 'ui_table_candidate',
}
CALLS = {
    0x2005d924: 'task_create', 0x20109bb4: 'photo_submit_1f03',
    0x20109b58: 'storage_submit_1f02', 0x2010a010: 'storage_submit_1f04',
    0x2010a090: 'storage_submit_1f04_extended', 0x2010a3c4: 'format_submit',
    0x2010a558: 'storage_cancel_candidate', 0x2010a534: 'storage_end_candidate',
}

def main():
    collect.preflight()
    rows, calls, sources, verified_bytes = [], [], {}, 0
    im = collect.Image()
    ins = re.compile(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$')
    for path in sorted((collect.ROOT / 'research/irom_storage/local').glob('section*.asm.txt')):
        sources[str(path.relative_to(collect.ROOT))] = collect.sha(path)
        regs = {}
        for line in path.read_text().splitlines():
            m = ins.match(line)
            if not m:
                continue
            pc, raw = int(m[1], 16), bytes.fromhex(m[2])
            assert im.raw(pc, len(raw)) == raw, (str(path), hex(pc))
            verified_bytes += len(raw)
            parts = re.split(r' -> | \|\| ', m[3])
            for index, op in enumerate(parts):
                name, _, tail = op.partition(' ')
                args = re.findall(r'@\([^)]*\)|[^,]+', tail)
                d = args[0] if args else ''
                if name == 'jl' and regs.get(d) in CALLS:
                    target = regs[d]
                    calls.append({'vma':hex(pc+2*index), 'target':hex(target), 'name':CALLS[target],
                        'known_args':{r:hex(regs[r]) for r in ('r4','r5','r6','r7') if r in regs},
                        'source':str(path.relative_to(collect.ROOT))})
                if name in ('ld', 'ldh', 'lduh', 'ldb', 'ldub', 'st', 'sth', 'stb') and len(args) > 1:
                    address = args[1]
                    mm = re.fullmatch(r'@\((-?\d+),(\w+)\)', address)
                    base = mm[2] if mm else address.removeprefix('@')
                    offset = int(mm[1]) if mm else 0
                    if base in regs:
                        target = (regs[base] + offset) & 0xffffffff
                        if target in FIELDS:
                            rows.append({'vma': hex(pc+2*index), 'target': hex(target),
                                'field': FIELDS[target], 'op': op, 'source': str(path.relative_to(collect.ROOT)),
                                'kind': 'write' if name.startswith('st') else 'read'})
                try:
                    if name == 'seth':
                        regs[d] = int(args[1].lstrip('#'), 0) << 16
                    elif name == 'ld24':
                        regs[d] = int(args[1], 16)
                    elif name == 'ldi':
                        regs[d] = int(args[1].lstrip('#'), 0) & 0xffffffff
                    elif name == 'mv' and args[1] in regs:
                        regs[d] = regs[args[1]]
                    elif name in ('or3', 'add3', 'and3') and args[1] in regs:
                        x, y = regs[args[1]], int(args[2].lstrip('#'), 0)
                        if name == 'add3' and 0x8000 <= y <= 0xffff:
                            y -= 0x10000
                        regs[d] = (x|y if name == 'or3' else x+y if name == 'add3' else x&y) & 0xffffffff
                    elif name in ('addi', 'slli', 'srli') and d in regs:
                        x, y = regs[d], int(args[1].lstrip('#'), 0)
                        regs[d] = (x+y if name == 'addi' else x<<y if name == 'slli' else x>>y) & 0xffffffff
                    elif name in ('jl', 'bl'):
                        for r in range(8):
                            regs.pop('r'+str(r), None)
                    elif name.startswith('b') or name in ('jmp', 'rte'):
                        regs.clear()
                    elif name not in ('nop', 'cmp', 'cmpu', 'cmpi', 'cmpui', 'cmpeq', 'st', 'sth', 'stb', 'push'):
                        regs.pop(d, None)
                except (ValueError, IndexError):
                    regs.clear()
    collect.save('field-candidates.json', {'status': 'PASS_BOUNDED_SCAN', 'verified_bytes': verified_bytes,
        'sources': sources, 'limitations': 'Linear disassembly includes data. No cross-block, alias, indirect or whole-program proof.',
        'rows': rows, 'calls': calls})
    counts = {name: sum(r['field'] == name for r in rows) for name in set(FIELDS.values())}
    print(json.dumps({'verified_bytes': verified_bytes, 'candidates': counts}, indent=2))
    for r in rows:
        if r['field'].startswith('storage_') and int(r['vma'],16) >= 0x20200000:
            print(json.dumps(r))
    for c in calls:
        print(json.dumps(c))

if __name__ == '__main__':
    main()
