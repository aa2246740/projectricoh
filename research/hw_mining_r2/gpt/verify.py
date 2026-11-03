#!/usr/bin/env python3
"""Verify official inputs, evidence bytes, and exact local checksum coverage."""
import argparse
import datetime
import json
import re
import runpy
import zipfile
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--record',action='store_true',help='write verification.json inside this directory')
p.add_argument('--seal',action='store_true',help='replace SHA256SUMS after verification')
args=p.parse_args()
x=runpy.run_path(str(Path(__file__).with_name('audit.py')))
out=x['OUT'];sha=x['sha'];inputs=json.loads((out/'inputs.json').read_text())
assert sha(x['ZIP'].read_bytes())==x['ZIP_SHA']==inputs['zip_sha256']
assert sha(x['OBJDUMP'].read_bytes())==inputs['objdump_sha256']
for name,r in inputs['members'].items():assert sha((out/'official'/name).read_bytes())==r['sha256'],name
extra_inputs=[]
for path in ('evidence/cross-unit-parameter-comparison.json','evidence/cross-unit-code-inputs.json'):
    if (out/path).exists():
        metadata=json.loads((out/path).read_text());assert metadata['zip_sha256']==x['ZIP_SHA']
        extra_inputs.extend(metadata['members'])
with zipfile.ZipFile(x['ZIP']) as official_zip:
    for r in extra_inputs:
        raw=official_zip.read(r['member']);assert sha(raw)==r['sha256']
        assert raw==(out/'official'/r['image']).read_bytes()
        if r['image'].endswith('3'):x['EXPECTED'][r['image']]=r['sha256']
ims={name:x['Image'](name) for name in x['EXPECTED']}

windows=0
for path in sorted((out/'evidence').glob('*.json')):
    m=json.loads(path.read_text())
    if not isinstance(m,dict) or not {'image','start','end','file_offset','sha256'}<=m.keys():continue
    im=ims[m['image']];start=int(m['start'],0);end=int(m['end'],0)
    raw=path.with_suffix('.bin').read_bytes()
    assert raw==im.read(start,end-start),path
    assert sha(raw)==m['sha256'] and im.offset(start)==int(m['file_offset'],0),path
    windows+=1

data_windows=0
for name,m in json.loads((out/'evidence/data-ranges.json').read_text()).items():
    raw=(out/'evidence'/f'{name}.bin').read_bytes();start=int(m['vma'],0)
    assert raw==ims['jlaunch3'].read(start,int(m['end'],0)-start),name
    assert sha(raw)==m['sha256'],name
    data_windows+=1

asm_files=asm_lines=0
pattern=re.compile(r'^\s*([0-9a-f]{7,8}):\t([0-9a-f ]+)\t')
for directory in ('disasm','evidence'):
    for path in sorted((out/directory).glob('*.asm')):
        names=[n for n in ims if path.name.startswith(n+'-')]
        assert len(names)==1,path
        im=ims[names[0]];count=0
        for line in path.read_text().splitlines():
            m=pattern.match(line)
            if not m:continue
            a=int(m[1],16);raw=bytes.fromhex(m[2]);assert raw
            assert raw==im.read(a,len(raw)),(path,hex(a))
            count+=1
        assert count,path
        asm_lines+=count;asm_files+=1

checks=json.loads((out/'evidence/byte-assertions.json').read_text())
for c in checks:
    a=int(c['vma'],0);raw=bytes.fromhex(c['expected'])
    assert ims['jlaunch3'].read(a,len(raw))==raw and c['passed'],c

result=dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    official_zip_sha256=x['ZIP_SHA'],official_members_verified=len(set(inputs['members'])|{r['image'] for r in extra_inputs}),
    objdump_sha256=inputs['objdump_sha256'],code_windows_verified=windows,data_windows_verified=data_windows,
    disassembly_files_verified=asm_files,disassembly_byte_lines_verified=asm_lines,
    explicit_byte_assertions_verified=len(checks),
    scope='Static bytes and evidence integrity only; no target execution, build, camera/card access, or pixel acceptance.')
if args.record:x['save']('verification.json',result)

manifest=out/'SHA256SUMS'
def files():
    found=[]
    for path in out.rglob('*'):
        assert not path.is_symlink(),path
        if path.is_file() and path!=manifest:found.append(path)
    return sorted(found,key=lambda z:z.relative_to(out).as_posix())
if args.seal:
    x['write']('SHA256SUMS',''.join(sha(path.read_bytes())+'  '+path.relative_to(out).as_posix()+'\n' for path in files()))
if manifest.exists():
    entries={}
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1);path=(out/name).resolve()
        assert path.is_relative_to(out) and path!=manifest and name not in entries,name
        assert sha(path.read_bytes())==digest,name
        entries[name]=digest
    assert set(entries)=={z.relative_to(out).as_posix() for z in files()},'manifest coverage differs'
    result['checksum_files_verified']=len(entries)
else:
    assert not args.seal
    result['checksum_files_verified']=None
print(json.dumps(result,ensure_ascii=False,indent=2))
