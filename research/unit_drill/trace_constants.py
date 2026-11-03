#!/usr/bin/env python3
"""Conservative linear constant candidates, not a control-flow proof."""
from pathlib import Path
import re
import struct
import subprocess
import sys
sys.dont_write_bytecode = True

# Local module is loaded by explicit file path, with no project imports.
import importlib.util
_spec=importlib.util.spec_from_file_location('drill_inspect',Path(__file__).with_name('inspect.py'))
m=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

RANGES=[(0x2012F40C,0x2012F960,'A'),(0x2012FF78,0x2013024E,'B'),
        (0x2012C5D4,0x2012D0B4,'colour'),(0x20181C44,0x20181CF8,'SysUnit-string'),
        (0x200759EC,0x20075A10,'checksum'),(0x20118468,0x2011846C,'tone-packer'),
        (0x2014BA84,0x2014BA88,'file-version-reader'),
        (0x20075BA0,0x20075BA4,'unit-integrity-validator'),
        (0x20063F64,0x20063F68,'body-unit-info-getter'),
        (0x20068388,0x2006838C,'body-version-getter'),
        (0x20089340,0x20089344,'body-file-check-status'),
        (0x20068A68,0x20068A6C,'body-set-update-mask')]


def main():
    hits=[];counts=[]
    for name in ('jlaunch3','jlaunch0','ilaunch3','ilaunch0'):
        b=(m.FW/name).read_bytes()
        for s in m.sections(b):
            raw=m.SCRATCH/f'{name}-constant-sec{s["index"]}.original-slice'
            m.write(raw,b[s['file']:s['file']+s['size']])
            command=[str(m.OBJDUMP),'-D','-b','binary','-m','m32r','-EB',
                     f'--adjust-vma={s["vma"]:#x}',str(raw)]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            regs={};n=0
            for line in result.stdout.splitlines():
                mat=re.match(r'\s*([0-9a-f]+):\s*((?:[0-9a-f]{2} +){1,4})\s*(.*)',line)
                if not mat:continue
                va=int(mat[1],16);at=s['file']+va-s['vma']
                rawbytes=bytes.fromhex(mat[2]);assert b[at:at+len(rawbytes)]==rawbytes
                n+=1
                for ins in re.split(r'\s*(?:->|\|\|)\s*',mat[3]):
                    op,*tail=ins.strip().split(None,1)
                    arg=tail[0] if tail else ''
                    parts=arg.split(',');dst=parts[0]
                    new=None;old=dict(regs);origin=[]
                    def imm(v):return int(v.lstrip('#'),0)
                    try:
                        if op=='seth':new=imm(parts[1])<<16
                        elif op in ('ld24','ldi'):new=imm(parts[1])
                        elif op=='mv' and parts[1] in old:
                            new=old[parts[1]][0];origin=old[parts[1]][1]
                        elif op in ('or3','add3','and3','xor3') and parts[1] in old:
                            v=old[parts[1]][0];k=imm(parts[2]);origin=old[parts[1]][1]
                            new={'or3':lambda:v|k,'add3':lambda:v+k,
                                 'and3':lambda:v&k,'xor3':lambda:v^k}[op]()
                        elif op=='addi' and dst in old:
                            new=old[dst][0]+imm(parts[1]);origin=old[dst][1]
                        elif op in ('add','or','and','sub') and all(p in old for p in parts[:2]):
                            v=old[dst][0];k=old[parts[1]][0];origin=old[dst][1]+old[parts[1]][1]
                            new={'add':lambda:v+k,'or':lambda:v|k,'and':lambda:v&k,'sub':lambda:v-k}[op]()
                        elif op in ('slli','srli') and dst in old:
                            v=old[dst][0];k=imm(parts[1]);origin=old[dst][1]
                            new=(v<<k) if op=='slli' else (v>>k)
                    except (ValueError,IndexError):pass
                    writes=(dst.startswith('r') or dst in ('lr','sp','fp')) and op not in (
                        'cmp','cmpu','cmpi','cmpui','beq','bne','st','stb','sth','push',
                        'jl','jmp','bgez','blez','bltz','bgtz','beqz','bnez','mvtc','mtc')
                    if writes:regs.pop(dst,None)
                    if new is not None:
                        new&=0xFFFFFFFF
                        org=(origin+[dict(vma=hex(va),file=hex(at),instruction=ins)])[-12:]
                        regs[dst]=(new,org)
                        for lo,hi,tag in RANGES:
                            if lo<=new<hi:
                                if op != 'seth':
                                    hits.append(dict(image=name,section=s['index'],vma=hex(va),file=hex(at),
                                        target=hex(new),tag=tag,instruction=ins,origin=org))
                    if op in ('jl','bl'):
                        for reg in [f'r{x}' for x in range(8)]+['lr']:regs.pop(reg,None)
                    if op in ('jmp','bra') or op.startswith('b'):
                        regs.clear()
            counts.append(dict(image=name,section=s['index'],lines=n,
                input_sha256=m.sha(b),slice_sha256=m.sha(b[s['file']:s['file']+s['size']]),
                file=hex(s['file']),vma=hex(s['vma']),size=s['size'],command=command))
    m.save('constant-references.json',dict(method='linear conservative constant tracking; clears at branches/calls; no dynamic/indirect completeness claim',sections=counts,hits=hits))
    for name in ('jlaunch3','jlaunch0','ilaunch3','ilaunch0'):
        for tag in ('A','B','colour','SysUnit-string','checksum','tone-packer','file-version-reader',
                    'unit-integrity-validator','body-unit-info-getter','body-version-getter','body-file-check-status'):
            rs=[r for r in hits if r['image']==name and r['tag']==tag]
            if rs:print(name,tag,len(rs),[(x['vma'],x['target']) for x in rs[:12]])


if __name__=='__main__':main()
