#!/usr/bin/env python3
"""Read-only M32R audit. Output is confined to this research directory.

Usage: python3 -I research/body_rpc8_probe/audit.py init|scan|verify
       python3 -I research/body_rpc8_probe/audit.py dump IMAGE START END LABEL
       python3 -I research/body_rpc8_probe/audit.py refs IMAGE ADDRESS ...
"""
import hashlib
from functools import cache
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRM = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'
TARGETS = [0x20065DB0, 0x20065914, 0x2007812C]

def write(name, obj):
    path = (HERE / name).resolve()
    assert path.is_relative_to(HERE)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def sha(data):
    return hashlib.sha256(data).hexdigest()

@cache
def image(name):
    assert name in ('ilaunch3', 'jlaunch3')
    b = (FIRM / name).read_bytes()
    segments = [dict(index=i, file_offset=x[0]+512, vma=x[1], size=x[2],
                     bss_vma=x[3], bss_size=x[4])
                for i in range(16)
                for x in [struct.unpack_from('>5I', b, 32 + 20*i)]]
    return b, segments

def offset(name, va):
    _, ss = image(name)
    for s in ss:
        if s['vma'] <= va < s['vma'] + s['size']:
            return s['file_offset'] + va - s['vma']
    raise ValueError(hex(va))

@cache
def rows(name):
    b, ss = image(name)
    out = []
    for p in sorted(DIS.glob(name+'-sec*.disasm.txt')):
        for no, line in enumerate(p.read_text().splitlines(), 1):
            t = line.split('\t')
            if len(t) < 3 or not re.fullmatch('[0-9a-f]+:',t[0].strip()):
                continue
            va = int(t[0].strip()[:-1],16)
            code = bytes.fromhex(t[1])
            seg = next(s for s in ss if s['vma'] <= va < s['vma']+s['size'])
            off = seg['file_offset'] + va-seg['vma']
            assert b[off:off+len(code)] == code, (name,hex(va))
            out.append(dict(vma=va,file_offset=off,hex=code.hex(),ins=t[2],
                            source=str(p.relative_to(ROOT)),line=no))
    return out

def dump(name, a, z, label, quiet=False):
    selected = [r for r in rows(name) if a <= r['vma'] < z]
    assert selected
    text = [f'# {name} [{a:#x},{z:#x}) SHA256={sha(image(name)[0])}',
            '# All listed instruction bytes were compared with the official binary.']
    for r in selected:
        text.append(f"{r['vma']:08x}: {r['hex']:12s} {r['ins']}  # file={r['file_offset']:#x}; {r['source']}:{r['line']}")
    p = HERE / 'evidence' / (label+'.txt')
    assert p.resolve().is_relative_to(HERE)
    p.write_text('\n'.join(text)+'\n')
    print(f'{label}: {len(selected)} byte-verified rows' if quiet else '\n'.join(text))

def refs(name, targets):
    """Conservative linear candidate finder, never a negative reachability proof."""
    registers = {}
    out = []
    for row in rows(name):
        for op in re.split(r'\s*(?:\|\||->)\s*',row['ins']):
            m = re.fullmatch(r'seth (\w+),#0x([0-9a-f]+)',op)
            if m:
                registers[m[1]]=int(m[2],16)<<16
                continue
            m = re.fullmatch(r'(ldi|ld24) (\w+),#?(-?\d+|0x[0-9a-f]+)',op)
            if m:
                registers[m[2]]=int(m[3],0)&0xffffffff
                continue
            m = re.fullmatch(r'(or3|add3) (\w+),(\w+),#(-?\d+|0x[0-9a-f]+)',op)
            if m:
                base=registers.get(m[3]); n=int(m[4],0)
                value=None if base is None else ((base|n) if m[1]=='or3' else (base+n))&0xffffffff
                registers[m[2]]=value
                if value in targets:
                    out.append(dict(row,target=hex(value),kind='address_construction',operation=op))
                continue
            m = re.fullmatch(r'mv (\w+),(\w+)',op)
            if m:
                registers[m[1]]=registers.get(m[2]); continue
            m = re.fullmatch(r'(jl|jmp) (\w+)',op)
            if m:
                value=registers.get(m[2])
                if value in targets:
                    out.append(dict(row,target=hex(value),kind='call' if m[1]=='jl' else 'jump',operation=op))
                if m[1]=='jl':
                    for i in range(8): registers['r'+str(i)]=None
                else: registers={}
                continue
            m = re.fullmatch(r'(bl|bra) (0x[0-9a-f]+)',op)
            if m:
                value=int(m[2],16)
                if value in targets:
                    out.append(dict(row,target=hex(value),kind='direct_'+m[1],operation=op))
                registers={}; continue
            m = re.match(r'(\w+) (r\d+|fp|lr|sp)(?:,|$)',op)
            if m and m[1] not in ['cmp','cmpu','cmpi','cmpui','beq','bne','beqz','bnez','push','st','stb','sth']:
                registers[m[2]]=None
    return out

def inventory():
    paths = list(FIRM.iterdir())
    paths += [ROOT / p for p in [
        'research/color_injection/REPORT.md','research/isp_pipeline/REPORT.md',
        'research/unit_drill/REPORT.md','research/focus_assist/REPORT.md',
        'research/stage1b_integration/RESIDENT_CACHE_CHECK.md',
        'firmware/recipe_fw/platform.c','firmware/recipe_fw/ui.c','firmware/recipe_fw/abi.S']]
    return {str(p.relative_to(ROOT)):dict(size=len(b),sha256=sha(b))
            for p in sorted(paths) if p.is_file() for b in [p.read_bytes()]}

def scan():
    b, ss = image('jlaunch3')
    raw=[]; lows=[]; branches=[]; decoded_branches=[]
    for target in TARGETS:
        needle=struct.pack('>I',target)
        for i in range(len(b)-3):
            if b[i:i+4]==needle:
                raw.append(dict(target=hex(target),file_offset=hex(i),alignment=i%4))
        for s in ss:
            block=b[s['file_offset']:s['file_offset']+s['size']]
            for i in range(0,len(block)-1,2):
                w=int.from_bytes(block[i:i+4],'big'); va=s['vma']+i
                # M32R long PC-relative BL/BRA, and short BL/BRA in either slot.
                if i+4<=len(block) and va%4==0 and (w>>24) in (0xfe,0xff):
                    d=w&0xffffff; d=d-(1<<24) if d&(1<<23) else d
                    if ((va&~3)+(d<<2))&0xffffffff==target:
                        branches.append(dict(target=hex(target),vma=hex(va),hex=block[i:i+4].hex(),encoding='BL24' if w>>24==0xfe else 'BRA24'))
                h=int.from_bytes(block[i:i+2],'big')
                if va%4==2: h &= 0x7fff
                if h>>8 in (0x7e,0x7f):
                    d=h&255; d=d-256 if d&128 else d
                    if ((va&~3)+(d<<2))&0xffffffff==target:
                        branches.append(dict(target=hex(target),vma=hex(va),hex=block[i:i+2].hex(),encoding='BL8' if h>>8==0x7e else 'BRA8'))
                if block[i+2:i+4]==struct.pack('>H',target&65535):
                    lows.append(dict(target=hex(target),vma=hex(va),file_offset=hex(s['file_offset']+i),hex=block[i:i+4].hex()))
    for row in rows('jlaunch3'):
        for op in re.split(r'\s*(?:\|\||->)\s*',row['ins']):
            m=re.fullmatch(r'(b\w+) .*?(0x[0-9a-f]+)',op)
            if m and int(m[2],16) in TARGETS:
                decoded_branches.append(dict(row,target=m[2],operation=op))
    data=dict(scope='Entire official jlaunch3 including 16 initialized segments and raw file',
        firmware_sha256=sha(b),segments=ss,
        methods=['Full-file every-byte BE32 target search',
                 'Every-halfword target-low-immediate inventory',
                 'Every-halfword BL8/BRA8 and aligned BL24/BRA24 target calculation',
                 'Byte-verified GNU disassembly and conservative linear constants'],
        limitations=['Dynamic RAM function pointers, computed addresses and external firmware remain unproved',
                     'Linear disassembly includes data and is not a control-flow proof'],
        raw_pointer_occurrences=raw,relative_branch_candidates=branches,
        decoded_control_transfer_candidates=decoded_branches,
        low_halfword_candidates=lows,constant_references=refs('jlaunch3',TARGETS))
    write('commit_scan.json',data)
    print(json.dumps({k:v for k,v in data.items() if k!='segments'},ensure_ascii=False,indent=2))

def verify():
    before=json.loads((HERE/'inputs_before.json').read_text())
    after=inventory(); assert before==after,'Protected input changed'
    count=0
    for p in (HERE/'evidence').glob('*.txt'):
        name=p.read_text().splitlines()[0].split()[1]
        if name not in ('ilaunch3','jlaunch3'): continue
        b,_=image(name)
        for line in p.read_text().splitlines():
            m=re.match(r'([0-9a-f]{8}): ([0-9a-f]+)\s+.*# file=(0x[0-9a-f]+);',line)
            if m:
                code=bytes.fromhex(m[2]); off=int(m[3],16)
                assert b[off:off+len(code)]==code,(p,line)
                assert offset(name,int(m[1],16))==off
                count+=1
    write('inputs_after.json',after)
    print(json.dumps(dict(protected_inputs=len(before),all_unchanged=True,excerpt_lines_verified=count)))

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='init':
        assert not (HERE/'inputs_before.json').exists()
        write('inputs_before.json',inventory())
    elif cmd=='dump': dump(sys.argv[2],int(sys.argv[3],0),int(sys.argv[4],0),sys.argv[5])
    elif cmd=='batch':
        for name,a,z,label in json.loads((HERE/sys.argv[2]).read_text()):
            dump(name,int(a,0),int(z,0),label,quiet=True)
    elif cmd=='refs': print(json.dumps(refs(sys.argv[2],set(int(s,0) for s in sys.argv[3:])),indent=2))
    elif cmd=='scan': scan()
    elif cmd=='verify': verify()
    else: raise ValueError(cmd)
