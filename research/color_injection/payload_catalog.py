#!/usr/bin/env python3
"""Candidate packet reads and fixed calls, with no firmware execution."""
from pathlib import Path
import json
import re
import runpy

HERE = Path(__file__).resolve().parent
A = runpy.run_path(str(HERE / 'analyze.py'))
LINES = list(A['lines']('jlaunch3'))

def scan(start):
    regs = {'r4': ('P', 0)}
    reads, calls = [], []
    for va, ins, *_ in LINES:
        if not start <= va < start + 4096:
            continue
        for op in re.split(r'\s*(?:\|\||->)\s*', ins):
            if op == 'jmp lr':
                return dict(start=hex(start), end=hex(va + 4), reads=reads, calls=calls)
            m = re.fullmatch(r'seth (\w+),#0x([0-9a-f]+)', op)
            if m:
                regs[m[1]] = ('K', int(m[2], 16) << 16)
                continue
            m = re.fullmatch(r'(ldi|ld24) (\w+),(?:#)?(-?\d+|0x[0-9a-f]+)', op)
            if m:
                regs[m[2]] = ('K', int(m[3], 0))
                continue
            m = re.fullmatch(r'(or3|add3) (\w+),(\w+),#(0x[0-9a-f]+|-?\d+)', op)
            if m:
                a, b = regs.get(m[3]), int(m[4], 0)
                regs[m[2]] = None if a is None else (a[0], a[1] | b if m[1] == 'or3' else a[1] + b)
                continue
            m = re.fullmatch(r'mv (\w+),(\w+)', op)
            if m:
                regs[m[1]] = regs.get(m[2])
                continue
            m = re.fullmatch(r'(ld\w*|st\w*) (\w+),@(?:\((-?\d+),(\w+)\)|(\w+))', op)
            if m:
                a = regs.get(m[4] or m[5])
                if m[1].startswith('ld') and a is not None and a[0] == 'P':
                    reads.append(dict(vma=hex(va),packet_offset=hex(a[1]+int(m[3] or 0)),load=m[1],instruction=op))
                if m[1].startswith('ld'):
                    regs[m[2]] = None
                continue
            m = re.fullmatch(r'jl (\w+)', op)
            if m:
                a = regs.get(m[1])
                if a is not None and a[0] == 'K':
                    calls.append(dict(vma=hex(va),target=hex(a[1]),packet_argument_r4=regs.get('r4') == ('P',0)))
                for i in range(8):
                    regs['r'+str(i)] = None
                continue
            if op.startswith(('jmp ', 'bra ', 'bl ')):
                regs = {}
                continue
            m = re.match(r'(\w+) (r\d+|fp|lr|sp)(?:,|$)',op)
            if m and m[1] not in ['cmp','cmpu','cmpi','cmpui','beqz','bnez','beq','bne','push','st','stb','sth']:
                regs[m[2]] = None
    return dict(start=hex(start),end=None,reads=reads,calls=calls)

result = []
for c in json.loads((HERE/'unit-commands.json').read_text()):
    row = dict(c)
    if c['handler']:
        s = scan(int(c['handler'],0))
        row['handler_candidates'] = s
        parsers = []
        for call in s['calls']:
            target=int(call['target'],0)
            if call['packet_argument_r4'] and 0x20197f68<=target<0x20199378:
                parsers.append(scan(target))
        row['parser_candidates']=parsers
    result.append(row)
(HERE/'command-payload-candidates.json').write_text(json.dumps(dict(evidence='未知: conservative linear scan, not complete CFG; exact code is in the byte-verified excerpts',commands=result),ensure_ascii=False,indent=2)+'\n')
for r in result:
    direct=r.get('handler_candidates',{}).get('reads',[])
    parsers=r.get('parser_candidates',[])
    print(r['command'],r['handler'],'direct='+','.join(x['packet_offset']+':'+x['load'] for x in direct),'parsers='+','.join(x['start'] for x in parsers),'parser_reads='+','.join(x['packet_offset']+':'+x['load'] for p in parsers for x in p['reads']))
