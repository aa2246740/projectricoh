#!/usr/bin/python3
"""Reuse the identity tools and audit the exact changed image ranges."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import types

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')
sys.path.insert(0,str(HERE))
import fixtures as F
sys.path.insert(0,str(ROOT/'research/review_body_v39/checks'))
from static_check import Elf,offset,target
from identity_compare import compare


def main():
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    baseline=F.prepare('baseline')
    (TEMP/'identity').mkdir(parents=True,exist_ok=True)
    os.environ['REVIEW_TEMP']=str(TEMP/'identity')
    path=ROOT/'research/review_body_v39/checks/identity_check.py'
    text=path.read_text()
    substitutions=[("ROOT / 'firmware/resident_v39/local/resident/build/resident.elf'",'Path('+repr(baseline['elf'])+')'),
                   ("ROOT / 'firmware/image_v39/local/ilaunch3'",'Path('+repr(baseline['body'])+')'),
                   ("ROOT / 'research/review_body_v39/evidence/identity-check.json'",'Path('+repr(str(HERE/'evidence/identity-tools.json'))+')')]
    for old,new in substitutions:assert text.count(old)==1;text=text.replace(old,new)
    namespace={'__name__':'window_identity_tools','__file__':str(path)}
    with contextlib.redirect_stdout(io.StringIO()):exec(compile(text,str(path),'exec'),namespace)
    identity_tools=json.loads((HERE/'evidence/identity-tools.json').read_text())
    assert identity_tools['status']=='PASS' and len(identity_tools['cases'])==5
    old=Elf(Path(baseline['elf']))
    assert old.sections['.resident']['data']==(ROOT/'firmware/resident_v39/local/resident/build/resident.bin').read_bytes()
    profiles=json.loads((HERE/'profiles.json').read_text())
    rows=[]
    original_hooks=(HERE/'options/baseline/linked_hooks.S').read_bytes()
    original_bridges=(ROOT/'firmware/resident_v39/resident/bridges.S').read_bytes()
    for name in profiles:
        if '_plus' in name:continue
        fixture=F.prepare(name);folder=HERE/'options'/name
        elf=Elf(Path(fixture['elf']));manifest=json.loads((folder/'patch-manifest.json').read_text())
        sections={k:v for k,v in elf.sections.items()if v['flags']&2 and v['bytes']}
        assert set(sections)=={'.resident','.root','.root_pins'}
        assert sections['.root']['address']==0x20054700 and sections['.root']['bytes']==244
        assert sections['.root_pins']['address']==0x200547f4 and sections['.root_pins']['bytes']==12
        assert sections['.root_pins']['data']==old.sections['.root_pins']['data']
        assert (folder/'linked_hooks.S').read_bytes()==original_hooks
        source=ROOT/'firmware/resident_v310_proto/options'/name/'resident'
        assert (source/'bridges.S').read_bytes()==original_bridges
        allowed=set(range(offset(0x2005276c),offset(0x20054800)))|set(range(0x16c,0x170))
        for h in manifest:
            address=int(h['address'],16);replacement=bytes.fromhex(h['replacement'])
            assert target(replacement[:4],address)==int(h['target'],16)
            assert replacement[0]==(0xfe if h['branch']=='bl' else 0xff)
            allowed.update(range(int(h['file_offset'],16),int(h['file_offset'],16)+h['length']))
        left=Path(baseline['body']).read_bytes();right=Path(fixture['body']).read_bytes()
        different=[i for i,(a,b)in enumerate(zip(left,right))if a!=b]
        assert not set(different)-allowed
        trust_address,trust_size=elf.symbols['rv_trust'];assert trust_size==80
        at=trust_address-0x2005276c
        assert sections['.resident']['data'][at:at+32]==bytes.fromhex(F.sha(F.OFFICIAL))
        rows.append(dict(name=name,code_bytes=sections['.resident']['bytes'],root_bytes=244,pin_bytes=12,
                         code_end=hex(sections['.resident']['address']+sections['.resident']['bytes']),
                         changed_body_bytes=len(different),outside_declared_ranges=0,pins_equal=True,
                         native_continuation_source_equal=True,elf_sha256=fixture['elf_sha256']))
    expected_rejection=False
    try:compare(Path(baseline['elf']),HERE/'options/neutral/build/resident.elf',
                Path(baseline['body']),Path(F.prepare('neutral')['body']))
    except AssertionError:expected_rejection=True
    assert expected_rejection
    result=dict(status='PASS',baseline_resident_byte_equal=True,identity_tools=identity_tools,
                identity_only_comparison_rejects_code_changes=True,images=rows,
                identity_tool_source_sha256=F.sha(path),identity_tool_executed_sha256=F.sha(text.encode()),
                identity_compare_sha256=F.sha(ROOT/'research/review_body_v39/checks/identity_compare.py'))
    (HERE/'evidence/identity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',images=len(rows),identity_cases=5,baseline_byte_equal=True)))


if __name__=='__main__':main()
