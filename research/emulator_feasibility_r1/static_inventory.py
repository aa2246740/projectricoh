#!/usr/bin/env python3
"""Byte-checked section map and conservative straight-line MMIO candidates."""
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/static'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
MASK = 0xffffffff


def reg(s):
    return {'sp': 15, 'fp': 13, 'lr': 14}.get(s, int(s[1:]) if re.fullmatch(r'r\d+', s) else -1)


def signed(x):
    return x - 2**32 if x & 0x80000000 else x


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    raw = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    sections, accesses = [], []
    byte_checks = 0
    rows_count = 0
    for i in range(16):
        src, va, size, bss, bn = struct.unpack_from('>5I', raw, 0x20+i*20)
        sections.append(dict(index=i, file_offset=src+512, vma=va, size=size, bss_address=bss, bss_size=bn))
        p = OUT / f'section-{i:02d}.bin'
        p.write_bytes(raw[src+512:src+512+size])
        d = p.with_suffix('.disasm.txt')
        if not d.exists():
            result = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                                     f'--adjust-vma={va}', str(p)], capture_output=True, text=True, check=True)
            d.write_text(result.stdout)
        text = d.read_text()
        known = {}
        prev_end = None
        for match in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$', text, re.M):
            pc, data, asm = int(match[1], 16), bytes.fromhex(match[2]), match[3]
            off = src+512+pc-va
            assert raw[off:off+len(data)] == data, ('objdump byte mismatch', i, hex(pc))
            byte_checks += len(data)
            rows_count += 1
            if prev_end != pc:
                known = {}
            prev_end = pc+len(data)
            parts = re.split(r' -> | \|\| ', asm)
            parallel = ' || ' in asm
            parallel_input = dict(known)
            barrier = False
            for slot, part in enumerate(parts):
                name, _, tail = part.partition(' ')
                args = re.findall(r'@\([^)]*\)|[^,]+', tail)
                dreg = reg(args[0]) if args else -1
                sreg = reg(args[1]) if len(args)>1 else -1
                inp = parallel_input if parallel else known
                value = None
                iv = lambda s: int(s.lstrip('#'), 0)
                is_mem = name in ('ld', 'ldub', 'lduh', 'ldb', 'ldh', 'st', 'stb', 'sth', 'lock', 'unlock')
                if is_mem and len(args) >= 2:
                    mem = args[1]
                    ma = re.fullmatch(r'@\((-?\d+),(\w+)\)', mem)
                    if ma:
                        base, delta = reg(ma[2]), int(ma[1])
                    elif mem.startswith('@') and reg(mem[1:]) >= 0:
                        base, delta = reg(mem[1:]), 0
                    else:
                        base, delta = -1, 0
                    if base in inp:
                        address = (inp[base]+delta)&MASK
                        if address >= 0xf0000000:
                            accesses.append(dict(section=i, pc=pc+2*slot, file_offset=off+2*slot,
                                                 address=address, operation=name, bundle=asm,
                                                 evidence='straight-line constant address; execution/reachability unknown'))
                try:
                    if name == 'seth':
                        value = iv(args[1]) << 16
                    elif name == 'ld24':
                        value = int(args[1], 16)
                    elif name == 'ldi':
                        value = iv(args[1])&MASK
                    elif name in ('mv', 'neg', 'not') and sreg in inp:
                        value = {'mv': lambda: inp[sreg], 'neg': lambda: -inp[sreg], 'not': lambda: ~inp[sreg]}[name]()&MASK
                    elif name in ('or3', 'and3', 'add3', 'xor3', 'sll3', 'srl3', 'sra3') and sreg in inp:
                        x,y = inp[sreg], iv(args[2])
                        value = {'or3': lambda:x|y, 'and3':lambda:x&y, 'add3':lambda:x+y,
                                 'xor3':lambda:x^y, 'sll3':lambda:x<<(y&31),
                                 'srl3':lambda:x>>(y&31), 'sra3':lambda:signed(x)>>(y&31)}[name]()&MASK
                    elif name in ('addi', 'slli', 'srli', 'srai') and dreg in inp:
                        x,y = inp[dreg], iv(args[1])
                        value = {'addi':lambda:x+y, 'slli':lambda:x<<y,
                                 'srli':lambda:x>>y, 'srai':lambda:signed(x)>>y}[name]()&MASK
                    elif name in ('add', 'sub', 'and', 'or', 'xor', 'sll', 'srl', 'sra') and dreg in inp and sreg in inp:
                        x,y = inp[dreg], inp[sreg]
                        value = {'add':lambda:x+y, 'sub':lambda:x-y, 'and':lambda:x&y,
                                 'or':lambda:x|y, 'xor':lambda:x^y, 'sll':lambda:x<<(y&31),
                                 'srl':lambda:x>>(y&31), 'sra':lambda:signed(x)>>(y&31)}[name]()&MASK
                except (ValueError, IndexError):
                    value = None
                writes_reg = name not in ('st','stb','sth','unlock','nop','cmp','cmpu','cmpi','cmpui','cmpeq','mvtc',
                                          'push','trap','rte') and not name.startswith('b') and name not in ('jl','jmp')
                if writes_reg and dreg >= 0:
                    if value is None:
                        known.pop(dreg, None)
                    else:
                        known[dreg] = value
                if name in ('push', 'pop'):
                    known.pop(15, None)
                if name.startswith('b') or name in ('jl', 'jmp', 'trap', 'rte'):
                    barrier = True
            if barrier:
                known = {}
    (OUT / 'sections.json').write_text(json.dumps(sections, indent=2)+'\n')
    def at(address,n):
        sec=next(s for s in sections if s['vma']<=address and address+n<=s['vma']+s['size'])
        off=sec['file_offset']+address-sec['vma']
        return raw[off:off+n],off
    modules=[]
    for i in range(100):
        address=0x200c0e60+i*40
        data,off=at(address,40)
        if data[0]==0:
            break
        modules.append(dict(index=i,vma=hex(address),file_offset=hex(off),
                            name=data[:32].split(b'\0')[0].decode('ascii','backslashreplace'),
                            init=hex(struct.unpack_from('>I',data,32)[0]),
                            finish=hex(struct.unpack_from('>I',data,36)[0])))
    (OUT/'native_driver_table.json').write_text(json.dumps(modules,indent=2)+'\n')
    (OUT / 'mmio_access_candidates.json').write_text(json.dumps(accesses, indent=2)+'\n')
    pages = {}
    for r in accesses:
        page = r['address']&~0xfff
        entry = pages.setdefault(page, {'page':hex(page), 'access_sites':0, 'addresses':set(), 'examples':[]})
        entry['access_sites'] += 1
        entry['addresses'].add(r['address'])
        if len(entry['examples'])<4:
            entry['examples'].append(r)
    rows=[]
    for k,e in sorted(pages.items()):
        e['addresses'] = [hex(a) for a in sorted(e['addresses'])]
        rows.append(e)
    (OUT / 'mmio_pages.json').write_text(json.dumps(rows, indent=2)+'\n')
    with (OUT / 'mmio_access_candidates.tsv').open('w') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['section','pc','file_offset','address','operation','bundle'])
        for r in accesses:
            w.writerow([r['section'],hex(r['pc']),hex(r['file_offset']),hex(r['address']),r['operation'],r['bundle']])
    summary={'sections':16,'byte_checked':byte_checks,'disassembly_rows':rows_count,'native_init_modules':len(modules),
             'static_mmio_candidates':len(accesses),'candidate_4k_pages':len(pages),
             'limitations':['Linear disassembly includes data. No whole-program reachability proof.',
                            'Constants propagate only within straight-line regions and stop at control flow.',
                            'Indirect register tables and dynamic aliases are not exhaustively counted.',
                            'A 4K page is not a physical device.']}
    (OUT / 'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    main()
