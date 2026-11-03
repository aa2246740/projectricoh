#!/usr/bin/env python3
"""Independent delivery checks, writing only to this research folder."""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FIRM=ROOT/'artifacts/firmware/gxr-1.51'
def sha(data): return hashlib.sha256(data).hexdigest()
def load(name): return json.loads((HERE/name).read_text())
def source(name):
    data=(FIRM/name).read_bytes()
    segments=[struct.unpack_from('>5I',data,32+20*i) for i in range(16)]
    return data,segments
def at(name,va,n):
    data,segments=images[name]
    for off,base,size,_,_ in segments:
        if base<=va and va+n<=base+size:
            return data[off+512+va-base:off+512+va-base+n]
    raise ValueError((name,hex(va),n))
images={name:source(name) for name in ['ilaunch3','jlaunch3']}
verification=load('verification.json')
for name,(data,_) in images.items():
    assert sha(data)==verification['source_identities'][name]['sha256']
before=load('inputs_before.json')
assert before==load('inputs_after.json')
for path,record in before.items():
    p=(ROOT/path).resolve(); assert p.is_relative_to(ROOT)
    data=p.read_bytes(); assert len(data)==record['size'] and sha(data)==record['sha256']
for name in ['t_commit_callers_audit.json','ram_injection_strategies.json','probe_design.json','verification.json']:
    assert isinstance(load(name),dict)
for p in HERE.glob('*.json'): json.loads(p.read_text())
for item in verification['instruction_byte_anchors']:
    assert at(item['image'],int(item['vma'],16),len(bytes.fromhex(item['hex']))).hex()==item['hex']
for item in load('ram_injection_strategies.json')['tables']:
    n=item['rows']*item['row_bytes']; data=at('jlaunch3',int(item['vma'],16),n)
    assert sha(data)==item['bytes_sha256'] and data[:item['row_bytes']].hex()==item['first_row_hex']
probe=load('probe_design.json')
for r in probe['primary_r_rom']['apply']:
    p=bytes.fromhex(r['request_pattern'].replace('??','00'))
    assert len(p)==20
    assert struct.unpack('>HBBIHHII',p)==(20,13,0,0,8,2,r['index'],r['value'])
curve=bytearray(at('jlaunch3',0x2012fffc,33))
assert curve[12:14]==bytes.fromhex('7680')
curve[13]=118
assert all(a<=b for a,b in zip(curve,curve[1:])) and curve[0]==0 and curve[-1]==255
assert probe['primary_r_rom']['apply_rpc_calls']==4
assert load('t_commit_callers_audit.json')['zero_persistence_proven'] is False
scan=load('commit_scan.json')
assert scan['decoded_control_transfer_candidates']==[]
assert not scan['relative_branch_candidates']

# Re-decode original segments with the existing, local GNU M32R binary.
# No package, tool installation, target execution or new firmware bytes.
objdump=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
jobs=[('jlaunch3',3,0x20116438,0x20116574,'fresh-peaking-first'),
      ('jlaunch3',3,0x20117af8,0x20117c2c,'fresh-peaking-second'),
      ('jlaunch3',3,0x20114150,0x201141c0,'fresh-matrix-selector'),
      ('jlaunch3',0,0x20065db0,0x20065e28,'fresh-t-commit'),
      ('ilaunch3',1,0x2009005c,0x200901ac,'fresh-body-rpc8')]
fresh=[]
for name,idx,start,end,label in jobs:
    off,base,size,_,_=images[name][1][idx]
    segment=ROOT/f'research/tooling_m32r/sections/{name}/sec{idx:02}-load-{base:08x}.bin'
    assert segment.read_bytes()==images[name][0][off+512:off+512+size]
    command=[str(objdump),'-D','-b','binary','-m','m32r','-EB',f'--adjust-vma={hex(base)}',
             f'--start-address={hex(start)}',f'--stop-address={hex(end)}',str(segment)]
    completed=subprocess.run(command,check=True,capture_output=True,text=True)
    out=HERE/'evidence'/f'{label}.txt'; out.write_text(completed.stdout)
    count=0
    for line in completed.stdout.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s*((?:[0-9a-f]{2} )+)\s*\t(.+)',line)
        if not m: continue
        va=int(m[1],16); code=bytes.fromhex(m[2]); assert at(name,va,len(code))==code
        # Match the actual decoded instruction text, not merely its bytes.
        source_dis=ROOT/f'research/tooling_m32r/disasm/{name}-sec{idx:02}-load-{base:08x}.disasm.txt'
        if count==0:
            expected={int(x.split(':',1)[0].strip(),16):x.split('\t')[2]
                for x in source_dis.read_text().splitlines()
                if re.match(r'^[0-9a-f]+:\t',x) and len(x.split('\t'))>=3}
        assert expected[va].strip()==m[3].strip(),(hex(va),expected[va],m[3])
        count+=1
    assert count>0
    fresh.append(dict(image=name,start=hex(start),end=hex(end),rows=count,
                      output=str(out.relative_to(HERE)),sha256=sha(out.read_bytes()),command=command))

report=(HERE/'REPORT.md').read_text(); links=[]
for target in re.findall(r'\]\(([^)]+)\)',report):
    if target.startswith(('https:','http:','#')): continue
    p=(HERE/target.split('#',1)[0]).resolve()
    assert p.is_relative_to(HERE) and p.is_file(),target
    links.append(target)
assert all(label in report for label in ['静态确认','推断','未知'])
assert not any(p.suffix.lower() in ['.bin','.elf','.o','.zip','.dat'] for p in HERE.rglob('*') if p.is_file())
verification['fresh_gnu_disassembly']=fresh
verification['report_local_links_checked']=len(links)
verification['independent_delivery_checks_passed']=True
verification['no_firmware_or_dat_output']=True
verification['report_sha256']=sha(report.encode())
(HERE/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(status='PASS_STATIC_CHECKS_ONLY',fresh_windows=len(fresh),
    fresh_instruction_rows=sum(x['rows'] for x in fresh),report_links=len(links),protected_inputs=len(before),
    camera_executed=False,zero_persistence_proven=False)))
