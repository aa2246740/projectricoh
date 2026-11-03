#!/usr/bin/env python3
"""Read-only firmware queries. Every output is confined to stage1_ui."""
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
D = (FIRM / 'ilaunch3').read_bytes()
SECS = [(s + 512, v, n) for s, v, n, _, _ in
        (struct.unpack_from('>IIIII', D, 32 + 20 * i) for i in range(16))]

def offset(va):
    for s, v, n in SECS:
        if v <= va < v + n:
            return s + va - v
    raise ValueError(f'unmapped {va:#x}')

def vma(off):
    return next((v + off - s for s, v, n in SECS if s <= off < s + n), None)

def rows(lo, hi):
    for i, (s, v, n) in enumerate(SECS):
        if not (lo < v + n and hi > v):
            continue
        p = next(DIS.glob(f'ilaunch3-sec{i:02d}-*.disasm.txt'))
        for no, line in enumerate(p.read_text().splitlines(), 1):
            m = re.match(r'^([0-9a-f]+):\t([0-9a-f ]+)\t(.+)$', line)
            if m and lo <= int(m[1], 16) < hi:
                va = int(m[1], 16)
                raw = bytes.fromhex(m[2])
                assert D[offset(va):offset(va)+len(raw)] == raw, hex(va)
                yield va, p.name, no, line

def dump(lo, hi, label=None):
    out = [f'# ilaunch3 VMA {lo:#x}..{hi:#x}; file {offset(lo):#x}..{offset(hi-1)+1:#x}; end exclusive.',
           '# Original disassembly filename:line | instruction. All machine bytes checked.']
    out += [f'{p}:{n} | {line}' for va, p, n, line in rows(lo, hi)]
    if label:
        assert re.fullmatch(r'[a-z0-9_-]+', label)
        (HERE / f'{label}.disasm.txt').write_text('\n'.join(out)+'\n')
        print(f'{label}: {len(out)-2} instructions')
    else:
        print('\n'.join(out))

def refs(lo, hi):
    candidates = []
    with (ROOT/'research/hidden_processing/ilaunch3-refs.tsv').open() as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if lo <= int(row['target'], 0) < hi:
                candidates.append(row)
    for off in range(0, len(D)-3):
        val = struct.unpack_from('>I', D, off)[0]
        if lo <= val < hi:
            va = vma(off)
            candidates.append({'source_vma':hex(va) if va else None,
                               'source_file_offset':hex(off), 'target':hex(val),
                               'kind':'raw_u32_candidate', 'aligned':off%4==0})
    print(json.dumps(candidates, indent=2))

def hexdump(lo, count):
    off = offset(lo)
    for i in range(0, count, 16):
        b = D[off+i:off+min(i+16, count)]
        print(f'{lo+i:08x} file={off+i:06x} {b.hex(" ")}')

def resource_find(text):
    d = (FIRM/'ilaunch4').read_bytes()
    gm = {int(k):v for k,v in json.loads((ROOT/'research/hidden_processing/glyph_map.json').read_text()).items()}
    # The partial map contains aliases, so scan both possible byte parities.
    matches = []
    for parity in (0,1):
        glyphs = [struct.unpack_from('>H',d,i)[0] for i in range(parity,len(d)-1,2)]
        dec = ''.join(gm.get(g,'\uFFFD') for g in glyphs)
        for m in re.finditer(re.escape(text), dec):
            off = parity+m.start()*2
            matches.append({'text':text,'file_offset':hex(off),'bytes':d[off:off+len(text)*2].hex(' ')})
    print(json.dumps(matches, indent=2))

def verify():
    checked = 0
    records = []
    original_files = {}
    for p in sorted(HERE.glob('*.disasm.txt')):
        for no,line in enumerate(p.read_text().splitlines(),1):
            m = re.search(r'\| ([0-9a-f]+):\t([0-9a-f ]+)\t(.+)$',line)
            if m:
                va = int(m[1],16); b = bytes.fromhex(m[2]); off = offset(va)
                assert D[off:off+len(b)] == b
                origin = line.split(' | ')[0]
                name, number = origin.rsplit(':', 1)
                if name not in original_files:
                    original_files[name] = (DIS/name).read_text().splitlines()
                assert original_files[name][int(number)-1] == line.split(' | ', 1)[1]
                records.append({'excerpt':p.name,'excerpt_line':no,'vma':hex(va),
                                'file_offset':hex(off),'original':origin,
                                'instruction':m[3]})
                checked += 1
    hashes = {n:hashlib.sha256((FIRM/n).read_bytes()).hexdigest() for n in ('ilaunch3','ilaunch4')}
    assert hashes['ilaunch3']=='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    assert hashes['ilaunch4']=='c9271288f8d395296623a3fe5358b2d83dec8730a89ed138a48ff8a2e8f14a5a'
    (HERE/'evidence_index.json').write_text(json.dumps(records,indent=2)+'\n')
    result = {'checked_instructions':checked,
              'unique_instruction_addresses':len({r['vma'] for r in records}),
              'original_disassembly_lines_checked':True,'input_sha256':hashes,
              'firmware_executed':False,'firmware_patched':False,'camera_connected':False}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

def main():
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest='command',required=True)
    dp=sp.add_parser('dump');dp.add_argument('lo',type=lambda x:int(x,0));dp.add_argument('hi',type=lambda x:int(x,0));dp.add_argument('label',nargs='?')
    rp=sp.add_parser('refs');rp.add_argument('lo',type=lambda x:int(x,0));rp.add_argument('hi',nargs='?',type=lambda x:int(x,0))
    hp=sp.add_parser('hex');hp.add_argument('lo',type=lambda x:int(x,0));hp.add_argument('count',type=lambda x:int(x,0))
    fp=sp.add_parser('find-text');fp.add_argument('text')
    sp.add_parser('verify')
    a=ap.parse_args()
    if a.command=='dump':dump(a.lo,a.hi,a.label)
    elif a.command=='refs':refs(a.lo,a.hi or a.lo+1)
    elif a.command=='hex':hexdump(a.lo,a.count)
    elif a.command=='find-text':resource_find(a.text)
    else:verify()

if __name__=='__main__':main()
