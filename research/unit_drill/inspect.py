#!/usr/bin/env python3
"""Offline evidence only. Run with python3 -I; never emits firmware images."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path('/Users/wu/.t3/projects/projectricoh')
OUT = ROOT / 'research/unit_drill'
SCRATCH = Path('/tmp/gxr_unit_drill').resolve()
FW = ROOT / 'artifacts/firmware/gxr-1.51'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def write(path, content):
    path = path.resolve()
    if not (path.is_relative_to(OUT) or path.is_relative_to(SCRATCH)):
        raise ValueError('write outside task allowlist')
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def save(name, obj):
    write(OUT / name, json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def u16(b, at):
    return struct.unpack_from('>H', b, at)[0]


def u32(b, at):
    return struct.unpack_from('>I', b, at)[0]


def sections(b):
    if u32(b, 0x160) == 0x27E00000:
        return [dict(index=0, file=0x200, vma=0x27E00000, size=len(b)-0x200)]
    out = []
    for i in range(16):
        source, load, size, bss, bss_size = struct.unpack_from('>5I', b, 0x20+20*i)
        if size and 0x200+source+size <= len(b):
            out.append(dict(index=i, file=0x200+source, vma=load, size=size,
                            bss=bss, bss_size=bss_size))
    return out


def offset(b, va):
    rows = [s for s in sections(b) if s['vma'] <= va < s['vma']+s['size']]
    if len(rows) != 1:
        raise ValueError(f'VMA {va:#x} has {len(rows)} mappings')
    return rows[0]['file']+va-rows[0]['vma']


def vmas(b, off):
    return [s['vma']+off-s['file'] for s in sections(b)
            if s['file'] <= off < s['file']+s['size']]


def disassemble(name, a, z, label):
    b = (FW / name).read_bytes()
    at = offset(b, a)
    assert offset(b, z-1) == at+z-a-1
    original = b[at:at+z-a]
    raw = SCRATCH / f'{name}-{label}.original-slice'
    write(raw, original)
    cmd = [str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
           f'--adjust-vma={a:#x}', str(raw)]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    lines = [f'# official {name} SHA256 {sha(b)}',
             f'# original slice file [{at:#x},{at+z-a:#x}) VMA [{a:#x},{z:#x})',
             f'# file = VMA - {a:#x} + {at:#x}',
             f'# original slice SHA256 {sha(original)}',
             '# command '+ ' '.join(cmd),
             '# Linear disassembly includes possible data. No target execution.']
    for line in result.stdout.splitlines():
        m = re.match(r'\s*([0-9a-f]+):', line)
        if m:
            va = int(m[1], 16)
            line = f'[file {at+va-a:08x}] '+line
        lines.append(line)
    write(OUT / 'evidence' / f'{name}-{label}.txt', '\n'.join(lines)+'\n')
    print(f'{name} {label}: file {at:#x}..{at+z-a:#x}; VMA {a:#x}..{z:#x}')


def xrefs():
    ranges = [(0x2012F40C, 0x2012F960, 'table-A'),
              (0x2012FF78, 0x2013024E, 'table-B'),
              (0x2012C5D4, 0x2012D0B4, 'colour-neighborhood'),
              (0x20181C3A, 0x20181D00, 'SysUnit-strings'),
              (0x200759EC, 0x20075A10, 'unit-checksum'),
              (0x20118468, 0x2011846C, 'tone-packer'),
              (0x2014BA84, 0x2014BA88, 'version-next-function')]
    rows = []
    for name in ('jlaunch3','jlaunch0','ilaunch3','ilaunch0'):
        b = (FW / name).read_bytes()
        for i in range(0, len(b)-3):
            val = u32(b, i)
            for lo, hi, tag in ranges:
                if lo <= val < hi:
                    rows.append(dict(file=name, kind='BE32-byte-scan',
                        at=hex(i), vma=[hex(x) for x in vmas(b,i)],
                        target=hex(val), tag=tag))
        for s in sections(b):
            for i in range(s['file'], s['file']+s['size']-3, 2):
                # seth rN,#imm16, then or3/add3 using that register.
                # This deliberately permissive candidate search does not prove
                # register liveness or reachability; manually review every hit.
                if b[i]&0xF0 != 0xD0 or b[i+1] != 0xC0:
                    continue
                reg = b[i]&15
                high = u16(b, i+2)<<16
                for j in range(i+4,min(i+1028,s['file']+s['size']-3),2):
                    if b[j]&0xF0 != 0x80 or b[j+1]&15 != reg:
                        continue
                    op = b[j+1]&0xF0
                    low = u16(b,j+2)
                    if op == 0xE0:
                        val = high|low
                    elif op == 0xA0:
                        val = (high+(low if low<0x8000 else low-65536))&0xFFFFFFFF
                    else:
                        continue
                    for lo,hi,tag in ranges:
                        if lo <= val < hi:
                            rows.append(dict(file=name,kind='seth-candidate',
                                at=hex(i),vma=[hex(x) for x in vmas(b,i)],
                                low_at=hex(j),low_vma=[hex(x) for x in vmas(b,j)],
                                distance=j-i,target=hex(val),tag=tag))
    save('xref-candidates.json',dict(method='all byte BE32; all mapped halfword seth + or3/add3 <=1024 bytes; no liveness proof',ranges=ranges,hits=rows))
    for tag in [x[2] for x in ranges]:
        print(tag, {name:sum(r['tag']==tag and r['file']==name for r in rows)
                    for name in ('jlaunch3','jlaunch0','ilaunch3','ilaunch0')})


def after():
    before=json.loads((OUT/'official-before.json').read_text())
    rows=[]
    for row in before['files']:
        b=(ROOT/row['path']).read_bytes()
        rows.append(dict(path=row['path'],size=len(b),sha256=sha(b),
                         unchanged=len(b)==row['size'] and sha(b)==row['sha256']))
    save('official-after.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    files=rows,all_unchanged=all(r['unchanged'] for r in rows)))
    print(sum(r['unchanged'] for r in rows),'/',len(rows),'unchanged')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('disasm','xrefs','after'))
    parser.add_argument('args',nargs='*')
    opts=parser.parse_args()
    if opts.mode=='disasm':
        name,a,z,label=opts.args
        disassemble(name,int(a,0),int(z,0),label)
    elif opts.mode=='xrefs':
        xrefs()
    else:
        after()
