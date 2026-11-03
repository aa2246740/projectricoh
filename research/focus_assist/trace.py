#!/usr/bin/env python3
"""Static-only firmware queries. Writes only to this new evidence directory.

Use python3 -I. No firmware execution, assembly, packaging or device access.
Existing disassembly is an index, not proof: dump verifies instruction bytes
against the official input. Reference TSV entries are linear candidates only.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRM = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'

def image(name):
    data = (FIRM / name).read_bytes()
    secs = [(s+512, v, n) for s,v,n,_,_ in
            (struct.unpack_from('>IIIII', data, 32+20*i) for i in range(16))]
    return data, secs

def mapped(secs, value, reverse=False):
    for off, va, size in secs:
        src, dst = (va, off) if reverse else (off, va)
        if src <= value < src+size:
            return dst+value-src
    return None

def dislines(name):
    for path in sorted(DIS.glob(name+'-sec*.disasm.txt')):
        for no, line in enumerate(path.read_text().splitlines(), 1):
            parts = line.split('\t')
            if len(parts) >= 3 and re.fullmatch('[0-9a-f]+:', parts[0]):
                yield int(parts[0][:-1],16), parts[2], path.name, no, line

def dump(name, start, end):
    data, secs = image(name)
    rows = [f'# {name} SHA-256 {hashlib.sha256(data).hexdigest()}',
            f'# VMA [{start:#010x},{end:#010x}); file [{mapped(secs,start,True):#x},{mapped(secs,end-1,True)+1:#x})',
            '# Original disassembly path: research/tooling_m32r/disasm/. Each instruction byte is checked against official input.']
    for va, ins, path, no, line in dislines(name):
        if start <= va < end:
            off = mapped(secs,va,True)
            raw = bytes.fromhex(line.split('\t')[1].replace(' ',''))
            assert data[off:off+len(raw)] == raw, (name,hex(va))
            rows.append(f'file={off:#08x} {path}:{no} | {line}')
    return '\n'.join(rows)+'\n'

def refs(name, target):
    data, secs = image(name)
    found = []
    path = ROOT/'research/hidden_processing'/f'{name}-refs.tsv'
    if path.exists():
        found.extend(dict(r, evidence='existing-linear-candidate') for r in
                     csv.DictReader(path.open(),delimiter='\t') if int(r['target'],0)==target)
    needle=struct.pack('>I',target); off=0
    while (off:=data.find(needle,off)) >= 0:
        va=mapped(secs,off)
        found.append({'evidence':'raw-big-endian-pointer','file_offset':hex(off),
                      'vma':hex(va) if va is not None else None})
        off+=1
    return found

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('op',choices=['dump','refs','data'])
    ap.add_argument('image')
    ap.add_argument('start',type=lambda x:int(x,0))
    ap.add_argument('end',type=lambda x:int(x,0),nargs='?')
    ap.add_argument('--save')
    a=ap.parse_args(); name={'i':'ilaunch3','j':'jlaunch3'}.get(a.image,a.image)
    if a.op=='dump': result=dump(name,a.start,a.end)
    elif a.op=='refs': result=json.dumps(refs(name,a.start),indent=2)+'\n'
    else:
        data,secs=image(name);start=mapped(secs,a.start,True);end=mapped(secs,a.end-1,True)+1
        result=f'# {name} VMA {a.start:#x}..{a.end:#x}, file {start:#x}..{end:#x}\n'
        for p in range(start,end,16):result+=f'file={p:#08x} VMA={mapped(secs,p):#010x} {data[p:min(p+16,end)].hex(" ")}\n'
    if a.save:
        dst=HERE/a.save
        assert dst.resolve().parent==HERE, 'Output must stay in focus_assist/'
        dst.write_text(result)
        print(f'{dst.name}: {len(result.splitlines())} lines')
    else:print(result,end='')

if __name__=='__main__':main()
