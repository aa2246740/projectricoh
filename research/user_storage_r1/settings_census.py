#!/usr/bin/env python3
"""Byte-checked linear candidate census, not a whole-program alias proof."""
from pathlib import Path
import collections
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

S = 0x2004a000
PTR = 0x200c0dac


def operand_mem(text, regs):
    m = re.fullmatch(r'@\((-?\d+),(\w+)\)', text)
    if m:
        base = regs.get(m[2])
        delta = int(m[1])
    else:
        m = re.fullmatch(r'@(r\d+|sp|fp|lr)(\+)?', text)
        if not m:
            return None
        base, delta = regs.get(m[1]), 0
    return (base[0], (base[1]+delta)&0xffffffff) if base else None


def main():
    collect.preflight()
    im = collect.Image()
    assert int.from_bytes(im.raw(PTR, 4), 'big') == S
    assert int.from_bytes(im.raw(PTR+4, 4), 'big') == 4096
    refs, accesses, arguments, files, loaded, raw_literals = [], [], [], [], 0, []
    for section in im.sections:
        path = collect.ROOT / ('research/irom_storage/local/section%02d.asm.txt' % section['index'])
        if not path.exists():
            folder=collect.OUT/'census'
            folder.mkdir(exist_ok=True)
            raw_path=folder/('section%02d.bin'%section['index'])
            raw_path.write_bytes(im.raw(section['vma'],section['size']))
            path=folder/('section%02d.asm.txt'%section['index'])
            path.write_text(subprocess.check_output(
                [str(collect.OBJDUMP),'-D','-b','binary','-m','m32r','-EB',
                 '--adjust-vma='+hex(section['vma']),str(raw_path)],text=True))
        regs, checked, lines = {}, 0, []
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$', line)
            if not m:
                continue
            pc, raw, asm = int(m[1], 16), bytes.fromhex(m[2]), m[3]
            assert im.raw(pc, len(raw)) == raw
            checked += len(raw)
            lines.append((pc, asm))
            for slot, op in enumerate(re.split(r' -> | \|\| ', asm)):
                op = re.sub(r' <[^>]*>', '', op).strip()
                parts = op.split(' ', 1)
                name = parts[0]
                args = re.findall(r'@\([^)]*\)|[^,]+', parts[1]) if len(parts) > 1 else []
                d = args[0] if args else ''
                loc = dict(pc=hex(pc+slot*2), section=section['index'], source_line=lineno, asm=op)
                value = None
                if name == 'seth':
                    value = ('const', int(args[1].lstrip('#'), 0)<<16)
                elif name == 'ld24':
                    value = ('const', int(args[1].lstrip('#'), 16))
                elif name == 'ldi':
                    value = ('const', int(args[1].lstrip('#'), 0)&0xffffffff)
                elif name == 'mv':
                    value = regs.get(args[1])
                elif name in ('add3', 'or3'):
                    base = regs.get(args[1])
                    n = int(args[2].lstrip('#'), 0)
                    if name == 'add3' and 0x8000 <= n <= 0xffff:
                        n -= 65536
                    if base and (name == 'add3' or base[0] == 'const'):
                        value = (base[0], (base[1]+n if name=='add3' else base[1]|n)&0xffffffff)
                elif name == 'addi':
                    base = regs.get(d)
                    if base:
                        value = (base[0], (base[1]+int(args[1].lstrip('#'), 0))&0xffffffff)
                elif name in ('ld', 'ldub', 'ldb', 'lduh', 'ldh', 'st', 'stb', 'sth'):
                    address = operand_mem(args[1], regs)
                    width = 4 if name in ('ld', 'st') else 2 if name in ('lduh', 'ldh', 'sth') else 1
                    if address:
                        if address == ('const', PTR):
                            refs.append(dict(**loc, kind='pointer_read' if name.startswith('ld') else 'pointer_write'))
                            if name == 'ld':
                                value = ('S', 0)
                        if address[0] == 'S' and address[1] < 4096:
                            accesses.append(dict(**loc,offset=address[1],width=width,
                                                 kind='read' if name.startswith('ld') else 'write'))
                    if args[1].endswith('+'):
                        base = args[1][1:-1]
                        old = regs.get(base)
                        if old:
                            regs[base] = (old[0], old[1]+width)
                    if name.startswith('st'):
                        continue
                elif name in ('jl', 'bl'):
                    if any(regs.get('r'+str(i), ('',0))[0] == 'S' for i in range(4,8)):
                        arguments.append(dict(**loc,registers={k:hex(v[1]) for k,v in regs.items()
                                                               if k in ('r4','r5','r6','r7') and v[0]=='S'},
                                              target=hex(regs[d][1]) if d in regs and regs[d][0]=='const' else d))
                    for k in tuple(regs):
                        if k in ('r0','r1','r2','r3','r4','r5','r6','r7'):
                            regs.pop(k, None)
                    continue
                elif name in ('jmp','bra','bc','bnc','beq','bne','beqz','bnez','bgtz','bltz','bgez','blez'):
                    regs.clear()
                    continue
                elif name.startswith('st') or name in ('nop','push','cmp','cmpu','cmpi','cmpui','cmpeq','mvtc'):
                    continue
                if d and re.fullmatch(r'r\d+|sp|lr|fp',d):
                    if value:
                        regs[d] = value
                    else:
                        regs.pop(d,None)
        files.append(dict(path=str(path.relative_to(collect.ROOT)),sha256=collect.sha(path),
                          verified_instruction_bytes=checked,linear_rows=len(lines)))
        loaded += checked
        # Literal pointer occurrences include tables/data and are candidates only.
        blob = im.raw(section['vma'], section['size'])
        for target in (S, PTR, PTR+4):
            needle = target.to_bytes(4,'big')
            start = 0
            while True:
                at = blob.find(needle,start)
                if at < 0:
                    break
                raw_literals.append(dict(target=hex(target),vma=hex(section['vma']+at)))
                start = at+1
    touched = sorted({x for a in accesses for x in range(a['offset'],min(4096,a['offset']+a['width']))})
    summary = dict(status='PASS_BOUNDED_CANDIDATE_CENSUS',sections=16,
                   pointer=hex(PTR),S=hex(S),bytes=4096,verified_disassembly_bytes=loaded,
                   direct_pointer_access_candidates=len(refs),S_access_candidates=len(accesses),
                   read_candidates=sum(a['kind']=='read' for a in accesses),
                   write_candidates=sum(a['kind']=='write' for a in accesses),
                   distinct_explicit_offset_bytes=len(touched),S_pointer_call_candidates=len(arguments),
                   certified_free_bytes=0,
                   limitations=['Linear disassembly contains data and unreachable paths.',
                                'Registers are forgotten at branches and call-clobbered registers at calls.',
                                'Indirect aliases, indexed accesses, cross-function arguments and pointer tables are incomplete.',
                                'Untouched offsets are not proved unused. Whole-block save reads all 4096 bytes.'])
    collect.save('settings-census.json',dict(summary=summary,inputs=files,pointer_refs=refs,
                                            explicit_accesses=accesses,S_arguments=arguments,
                                            raw_pointer_literals=raw_literals,touched_offsets=touched))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
