#!/usr/bin/env python3
"""Verify report evidence against real official bytes, not just generated JSON."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import struct
import zipfile
import sys
sys.dont_write_bytecode = True

spec=importlib.util.spec_from_file_location('drill',Path(__file__).with_name('inspect.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def main():
    before=json.loads((m.OUT/'official-before.json').read_text())
    after=json.loads((m.OUT/'official-after.json').read_text())
    assert len(before['files'])==30 and after['all_unchanged']
    assert len(after['files'])==30 and all(x['unchanged'] for x in after['files'])
    for row in before['files']:
        b=(m.ROOT/row['path']).read_bytes()
        assert len(b)==row['size'] and m.sha(b)==row['sha256']
    # Compare every extracted official input with its ZIP member in memory.
    matches=[]
    with zipfile.ZipFile(m.ROOT/'artifacts/downloads/gxr-151.zip') as archive:
        members={Path(i.filename).name:i for i in archive.infolist() if not i.is_dir()}
        official=[r for r in before['files'] if r['path'].startswith('artifacts/firmware/')]
        assert len(official)==29
        for row in official:
            name=Path(row['path']).name
            raw=archive.read(members[name]);assert m.sha(raw)==row['sha256']
            matches.append(name)
    disasm=[];total=0
    for p in sorted((m.OUT/'evidence').glob('*.txt')):
        text=p.read_text();match=re.search(r'# official (\w+) SHA256 (\w+)',text);assert match
        name,digest=match.groups();raw=(m.FW/name).read_bytes();assert m.sha(raw)==digest
        window=re.search(r'# original slice file \[(0x[0-9a-f]+),(0x[0-9a-f]+)\) VMA \[(0x[0-9a-f]+),(0x[0-9a-f]+)\)',text)
        assert window
        a,z,va,vz=map(lambda x:int(x,16),window.groups());assert z-a==vz-va
        assert m.offset(raw,va)==a and m.offset(raw,vz-1)==z-1
        slice_digest=re.search(r'# original slice SHA256 (\w+)',text)[1]
        assert m.sha(raw[a:z])==slice_digest
        n=0
        for line in text.splitlines():
            mat=re.match(r'\[file ([0-9a-f]+)\]\s*([0-9a-f]+):\s*((?:[0-9a-f]{2} +){1,4})',line)
            if not mat:continue
            off=int(mat[1],16);address=int(mat[2],16);bs=bytes.fromhex(mat[3])
            assert off==a+address-va and raw[off:off+len(bs)]==bs
            n+=1
        disasm.append(dict(path=str(p.relative_to(m.OUT)),image=name,instruction_records=n,bytes=z-a))
        total+=n
    b=(m.FW/'jlaunch3').read_bytes();B=m.offset(b,0x2012FF78)
    proposals=json.loads((m.OUT/'curve-proposals.json').read_text())
    assert m.sha((m.ROOT/proposals['reference_path']).read_bytes())==proposals['reference_sha256']
    for option in proposals['options']:
        values=option['proposed_output'];assert len(values)==33
        assert values[0]==0 and values[-1]==255 and all(x<=y for x,y in zip(values,values[1:]))
        assert all(0<=x<=255 for x in values)
        delta=0
        for k,p in enumerate(option['byte_table']):
            assert int(p['file'],16)==B+k and b[B+k]==int(p['old'],16)
            assert int(p['new'],16)==values[k]
            delta+=(values[k]-b[B+k])*((B+k-0x200)%6+2)
        checksum=(m.u32(b,0x16c)+delta)&0xFFFFFFFF
        assert checksum==int(option['new_checksum'],16)
        assert all(int(p['new'],16)==struct.pack('>I',checksum)[k]
                   for k,p in enumerate(option['checksum_header_bytes']))
    report=(m.OUT/'REPORT.md').read_text();assert report.startswith('BLOCKED')
    links=[]
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',report):
        if '://' in target:continue
        path=target.split('#')[0]
        if not path:continue
        real=(m.OUT/path).resolve();assert real.is_relative_to(m.ROOT)
        # verification.json itself is written at the end of this check.
        if path=='verification.json':continue
        assert real.exists(),path
        links.append(path)
    scripts=[]
    for p in sorted(m.OUT.glob('*.py')):
        ast.parse(p.read_text(),filename=str(p));scripts.append(p.name)
    unexpected=[str(p.relative_to(m.OUT)) for p in m.OUT.rglob('*')
                if p.is_file() and p.suffix not in ('.py','.md','.json','.txt','.tsv')]
    assert not unexpected,unexpected
    # Every reported research snapshot still matches the files just checked.
    changed=[]
    for row in json.loads((m.OUT/'research-inputs.json').read_text()):
        raw=(m.ROOT/row['path']).read_bytes()
        if m.sha(raw)!=row['sha256']:changed.append(row['path'])
    assert not changed,changed
    result=dict(status='PASS for offline evidence; U0 remains BLOCKED',
        official_files_unchanged='30/30',zip_members_match_extracted=len(matches),
        disassembly_windows=len(disasm),disassembly_machine_code_records=total,
        disassembly=disasm,curve_options_checked=2,syntax_checked=scripts,
        local_report_links_checked=len(links),research_snapshots_unchanged=True,
        firmware_output_files_created=0,firmware_build_or_execution=False,
        note='No camera, flash, rescue, boot, or visual acceptance is asserted.')
    m.save('verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='disassembly'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
