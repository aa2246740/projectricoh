#!/usr/bin/env python3
"""复核受保护输入、提取字节、反汇编字节行与静态结论。"""
import json
import re
import runpy
import zipfile
from pathlib import Path

S = runpy.run_path(str(Path(__file__).with_name('collect.py')))
OUT, ROOT, Image, sha = S['OUT'], S['ROOT'], S['Image'], S['sha']


def verify():
    before=json.loads((OUT/'inputs_before.json').read_text())
    for name,digest in before.items():
        assert sha((ROOT/name).read_bytes())==digest,name
    inputs=json.loads((OUT/'evidence/official_inputs.json').read_text())
    assert inputs['archive_sha256']==S['ARCHIVE_SHA']
    assert sha(S['ARCHIVE'].read_bytes())==S['ARCHIVE_SHA']
    with zipfile.ZipFile(S['ARCHIVE']) as archive:
        for m in inputs['members']:
            raw=(OUT/'official'/m['name']).read_bytes()
            assert raw==archive.read(m['member']) and sha(raw)==m['sha256']
    count=0;byte_lines=0;incomplete=[];instructions={}
    for p in sorted((OUT/'evidence').glob('*.asm')):
        meta=p.with_suffix('.json')
        assert meta.exists(),p.name
        d=json.loads(meta.read_text())
        raw=p.with_suffix('.bin').read_bytes()
        im=Image(d['member']);address=int(d['vma'],16)
        assert len(raw)==d['size'] and sha(raw)==d['bytes_sha256']
        assert sha(im.data)==d['member_sha256']
        assert im.offset(address,len(raw))==int(d['file'],16)
        assert im.read(address,len(raw))==raw
        covered=set()
        for line in p.read_text().splitlines():
            m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+){1,4})',line)
            if not m:
                continue
            offset=int(m[1],16)-address;b=bytes.fromhex(m[2])
            assert offset>=0 and raw[offset:offset+len(b)]==b,(p.name,line)
            covered.update(range(offset,offset+len(b)));byte_lines+=1
            text=line[m.end():].strip().lower()
            instructions[(d['member'],address+offset)]=re.sub(r'\s+',' ',text)
        missing=sorted(set(range(len(raw)))-covered)
        if missing:
            incomplete.append(dict(file=p.name,vma=[hex(address+i) for i in missing],
                                   raw=bytes(raw[i] for i in missing).hex()))
        count+=1
    assert incomplete == [dict(file='jlaunch3-segment-03.asm',
                              vma=['0x20147328','0x20147329'],raw='0400')],incomplete
    materials=json.loads((OUT/'evidence/material_checks.json').read_text())
    assert sum(x['count'] for x in materials)==943 and all(x['ok'] for x in materials)
    six=json.loads((OUT/'evidence/six_units.json').read_text())
    assert len(six)==6 and all(x['script_fields']==bytes(13).hex() and
        x['mirror_bytes']==bytes(16).hex() and not x['raw_wrapper_pointers'] for x in six)
    calls=json.loads((OUT/'evidence/calls.json').read_text())['calls']
    assert not calls['0x201123d4'] and not calls['0x201123b0']
    assert [x['pc'] for x in calls['0x20113954']]==['0x2010c388']
    assert len([x for x in calls['0x20255600'] if x['r4']==11])==1
    maps=json.loads((OUT/'evidence/product_maps.json').read_text())
    assert maps['generation']==117 and len(maps['units'])==3
    assert sum(len(x['rows']) for x in maps['units'])==27
    report=(OUT/'VALIDATION.md').read_text()
    report_rows=0
    for line in report.splitlines():
        m=re.match(r'^([0-9A-Fa-f]{8}):\s+((?:[0-9a-f]{2}\s+){1,4})\s*(.*)',line)
        if not m:
            continue
        a=int(m[1],16);raw=bytes.fromhex(m[2]);text=re.sub(r'\s+',' ',m[3].strip().lower())
        assert Image('jlaunch3').read(a,len(raw))==raw,line
        assert instructions[('jlaunch3',a)]==text,line
        report_rows+=1
    assert report_rows==91
    for link in re.findall(r'\]\(([^)]+)\)',report):
        assert (OUT/link).exists(),link
    return dict(status='PASS',protected_inputs=len(before),protected_inputs_unchanged=True,
                material_manifest_entries=943,official_members=len(inputs['members']),
                disassembly_files=count,verified_byte_lines=byte_lines,
                report_instruction_rows=report_rows,report_links='PASS',
                undecoded_tail=incomplete,six_unit_zero_fields='PASS',
                product_map_rows=27,product_map_scope='PASS',
                scope='离线静态字节与源码核验；没有执行目标固件、构建或连接相机。')


if __name__=='__main__':
    result=verify()
    S['save']('evidence/verification.json',result)
    print(json.dumps(result,ensure_ascii=False))
