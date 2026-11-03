#!/usr/bin/env python3
"""Create bounded evidence excerpts from official bytes and saved disassembly.

Run with python3 -I. Does not execute or modify firmware, or run project scripts.
Writes only in research/unit_recovery/. Requires inspect.py disassembly outputs.
"""
from pathlib import Path
import collections
import hashlib
import json
import re
import runpy
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
M = runpy.run_path(str(HERE / 'inspect.py'))
FW, OUT = M['FW'], M['OUT']
W = M['write']
E = OUT / 'evidence'

# Each window is a bounded observation, not a complete control-flow proof.
WINDOWS = {
 '01-body-ui.txt': ('ilaunch3', [(0x2036d6bc,0x2036d720),(0x2036d8e0,0x2036da60),(0x2036f9ec,0x2036feec)]),
 '02-body-transfer.txt': ('ilaunch3', [(0x2009005c,0x200901a0),(0x20090ab8,0x20090af4),(0x2010d4b4,0x2010d714),(0x2010d838,0x2010d9e0)]),
 '03-unit-receiver.txt': ('jlaunch3', [(0x2008006c,0x20080328),(0x2008041c,0x20080540),(0x20080d54,0x20080dd8),(0x20080e44,0x20080f28),(0x20081344,0x20081378)]),
 '04-unit-command-registration.txt': ('jlaunch3', [(0x20058124,0x2005819c),(0x2014bfc8,0x2014c040),(0x2007ad38,0x2007ae70),(0x2007c630,0x2007c6c8)]),
 '05-unit-file-check.txt': ('jlaunch3', [(0x2007a47c,0x2007a554),(0x2007a6a8,0x2007aa88),(0x2007ac70,0x2007ad38)]),
 '06-unit-writer.txt': ('jlaunch3', [(0x2007bcb0,0x2007c000),(0x2007c000,0x2007c39c),(0x20077540,0x20077808),(0x20077808,0x20077a84)]),
 '07-storage-dispatch.txt': ('jlaunch3', [(0x20077a84,0x2007812c),(0x2008c27c,0x2008c368)]),
 '08-checksum-header.txt': ('jlaunch3', [(0x200750c8,0x200751c8),(0x200759ec,0x20075c0c)]),
 '09-backup-receiver.txt': ('jlaunch0', [(0x27e00000,0x27e000dc),(0x27e19968,0x27e199c0),(0x27e2c180,0x27e2c260),(0x27e3a528,0x27e3a660),(0x27e3be18,0x27e3be6c),(0x27e3c390,0x27e3c3cc),(0x27e3f610,0x27e3faf0)]),
 '10-adjcom-interpreter.txt': ('jlaunch3', [(0x2007b9c0,0x2007bb58),(0x2005ad3c,0x2005ad78),(0x2005ae30,0x2005b098)]),
 '11-unit-staging.txt': ('jlaunch3', [(0x2014b830,0x2014b95c),(0x2014b95c,0x2014ba84),(0x2014bcc4,0x2014bd94)]),
 '12-body-model-info.txt': ('ilaunch3', [(0x200637e0,0x20063894),(0x20063a28,0x20063ad4),(0x20063f64,0x20063f84)]),
 '14-type-labels.txt': ('jlaunch3', [(0x200789d8,0x20078bf0),(0x20078c00,0x20078fb4)]),
}


def excerpts():
    cache = {}
    for output, (name, windows) in WINDOWS.items():
        if name not in cache:
            by_va = {}
            for p in sorted((OUT / 'disasm').glob(name + '-*.txt')):
                for line in p.read_text().splitlines():
                    m = re.match(r'\[file ([0-9a-f]+)\]\s*([0-9a-f]+):',line)
                    if m:
                        by_va.setdefault(int(m[2],16), (line,p.name))
            cache[name] = by_va
        b = (FW / name).read_bytes()
        head = [f'# 静态确认：{name}; SHA256={hashlib.sha256(b).hexdigest()}',
                '# 线性反汇编摘录；数据区被解码为指令不代表该区会执行。',
                '# 每行同时保留文件偏移和 VMA。箭头/并行格式来自 M32R objdump。']
        for start, end in windows:
            off = M['fileoff'](b,start)
            head.append(f'\n## VMA [{start:#010x},{end:#010x}), file [{off:#x},{off+end-start:#x})')
            lines = [(v,*cache[name][v]) for v in sorted(cache[name]) if start <= v < end]
            if not lines:
                raise RuntimeError(f'Missing disassembly window {name} {start:#x}')
            head.append('# Source: ' + ', '.join(sorted({x[2] for x in lines})))
            head.extend(x[1] for x in lines)
        W(E / output, '\n'.join(head)+'\n')


def derived():
    rows = []
    for name in ('jlaunch0','jlaunch3','jlaunch4','jlaunch8'):
        b = (FW / name).read_bytes()
        n = M['be32'](b,0x164)
        source = M['be32'](b,0x20)
        # Exact byte-weight function found in both MAIN and BACKUP.
        calc = sum(sum(b[0x200+k:0x200+n:6])*(((source+k)%6)+2) for k in range(6)) & 0xffffffff
        rows.append(dict(file=name,sha256=M['sha'](b),bytes=len(b),
            magic_low7=bytes(x&127 for x in b[:16]).decode('ascii'),
            end_magic_low7=bytes(x&127 for x in b[0x1f0:0x200]).decode('ascii'),
            type=b[0x10],form=b[0x11],version=f'{struct.unpack_from(">H",b,0x12)[0]:04X}',
            version_low=f'{struct.unpack_from(">H",b,0x14)[0]:04X}',
            compatible_version=f'{struct.unpack_from(">H",b,0x16)[0]:04X}',
            source_20=source,entry_160=M['be32'](b,0x160),payload_size=n,
            file_size_168=M['be32'](b,0x168),stored_checksum=M['be32'](b,0x16c),
            calculated_checksum=calc,checksum_matches=calc==M['be32'](b,0x16c),
            flags={f'{x:#x}':M['be32'](b,x) for x in range(0x170,0x184,4)}))
    M['save']('a12-header-summary.json',rows)
    b = (FW/'jlaunch8').read_bytes()
    payload = b[0x200:]
    lines = payload.decode('cp932').splitlines()
    facts = dict(payload_sha256=M['sha'](payload),line_count=len(lines),
        text_encoding='cp932 (command bytes are ASCII; one comment contains Japanese)',
        opcode_counts=dict(collections.Counter(s[:1] for s in lines if s)),
        first_lines=lines[:12],last_lines=lines[-8:],
        comments=[dict(line_number=i+1,text=s) for i,s in enumerate(lines) if s.startswith(('#',';'))])
    M['save']('jlaunch8-command-census.json',facts)
    W(OUT/'jlaunch8-payload.txt',payload)

    j = (FW/'jlaunch3').read_bytes()
    tables = {}
    for key,va,base,n in [('type-label',0x200bf4c8,0x20078a00,13),
                           ('storage-area',0x200bf470,0x20077abc,14),
                           ('storage-callback',0x200bf48c,0x20077f08,14),
                           ('packet-kind',0x200c0c06,0x20080218,37)]:
        off=M['fileoff'](j,va)
        tables[key]=[dict(index=i+1,table_vma=f'{va+2*i:#010x}',file_offset=f'{off+2*i:#x}',
                         destination=f'{base+struct.unpack_from(">h",j,off+2*i)[0]:#010x}') for i in range(n)]
    M['save']('decoded-dispatch-tables.json',tables)

    probes=[('jlaunch3',0x20181c3a,0x20181cb0),('jlaunch3',0x200b2d00,0x200b2d90),
            ('jlaunch3',0x200c50e8,0x200c5188),('ilaunch3',0x201412ac,0x2014132a),
            ('jlaunch0',0x27e7f121,0x27e7f1c0),('jlaunch0',0x27e7c621,0x27e7c6d0)]
    out=['# 静态确认：官方字节摘录；用途解释见 REPORT.md。']
    for name,a,z in probes:
        data=(FW/name).read_bytes();p=M['fileoff'](data,a)
        out.append(f'\n## {name} VMA {a:#x}, file {p:#x}; SHA256={M["sha"](data)}')
        for k in range(0,z-a,16):
            s=data[p+k:p+min(k+16,z-a)]
            asc=''.join(chr(x) if 32<=x<127 else '.' for x in s)
            out.append(f'{a+k:08x} [file {p+k:08x}]: {s.hex(" ")} {asc}')
    W(E/'13-data-and-labels.txt','\n'.join(out)+'\n')

    ext=(FW/'jlaunch4').read_bytes()
    markers=[]
    for q in re.finditer(b'\xff[\xc0-\xc3]',ext[0x204:]):
        p=q.start()+0x204
        if p+9 <= len(ext):
            markers.append(dict(file_offset=hex(p),marker=hex(ext[p+1]),
                precision=ext[p+4],height=struct.unpack_from('>H',ext,p+5)[0],
                width=struct.unpack_from('>H',ext,p+7)[0]))
    M['save']('jlaunch4-resource-probe.json',dict(sha256=M['sha'](ext),
        prefix_200=ext[0x200:0x220].hex(),first_word=M['be32'](ext,0x200),
        jpeg_soi_file_offset=hex(ext.find(b'\xff\xd8',0x200)),
        jpeg_sof_candidates=markers,
        limitation='Marker scan only; does not prove all payload bytes are JPEG resources.'))

    refs=[]
    for name,target in [('jlaunch3',0x20181c44),('jlaunch3',0x20181c69),
                        ('jlaunch3',0x20181c8d),('ilaunch3',0x200cecf3),
                        ('jlaunch3',0x200c50f8),('jlaunch3',0x20181c3a),
                        ('jlaunch0',0x27e7c680)]:
        raw=subprocess.check_output([sys.executable,'-I',str(HERE/'query.py'),
                                     'xref',name,hex(target)],text=True)
        refs.append(json.loads(raw))
    M['save']('bounded-xrefs.json',refs)

    commands=[]
    for p in sorted(OUT.glob('*-disasm.json')):
        rows=json.loads(p.read_text())
        if all(x['tag'].startswith('sec') for x in rows):
            commands.append(['python3','-I','research/unit_recovery/inspect.py','disasm',rows[0]['file']])
        else:
            for x in rows:
                commands.append(['python3','-I','research/unit_recovery/inspect.py','disasm',x['file'],
                                 '--start',hex(x['vma']),'--end',hex(x['vma']+x['size']),'--label',x['tag']])
    M['save']('disassembly-commands.json',dict(commands=commands,
        limitation='Commands extract unchanged official bytes and disassemble them. No target execution or firmware building.'))


if __name__ == '__main__':
    excerpts()
    derived()
    print(f'Created {len(WINDOWS)+1} bounded evidence files; checksums decoded without changing firmware.')
