"""Final artifact checks, host-only staging, reports and complete checksums."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
IMAGE=ROOT/'firmware/image_v33'
ENGINE=HERE/'acceptance/local/full-r8'
PHASES=('legacy','historical','behavior','faults','additional','reviewer','boundary','policy','upgrade','first-frame','actual-upgrade')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def mapped(body,va,n):
    matches=[]
    for i in range(16):
        src,base,size,_,_=struct.unpack_from('>5I',body,32+20*i)
        if base<=va and va+n<=base+size:matches.append(512+src+va-base)
    assert len(matches)==1
    return matches[0]


def inspect():
    load_module(HERE/'prepare.py','frozen_delivery').guard()
    original=ROOT/'firmware/resident_v32'
    objects={}
    for name in ('resident.o','loader.o','shared.o','runtime.o','bridges.o','validate_envelope.inc.o'):
        a=HERE/'local/resident/build'/name;b=original/'local/resident/build'/name
        assert a.read_bytes()==b.read_bytes();objects[name]=sha(a)
    for name in ('abi.h','resident.h','gxrce.h','bridges.S'):
        assert (HERE/'resident'/name).read_bytes()==(original/'resident'/name).read_bytes()
    assert (LOCAL/'resident/linked_hooks.S').read_bytes()==(original/'local/resident/linked_hooks.S').read_bytes()
    # Only the adapter changes engine behavior. Header changes relocate includes.
    engine_changes=[];include_changes=[]
    source=ROOT/'firmware/engine_v33d'
    for path in (HERE/'acceptance').rglob('*'):
        relative=path.relative_to(HERE/'acceptance')
        if 'local' in relative.parts or path.suffix not in ('.c','.h','.S') or not (source/relative).is_file():continue
        if relative.parts[0] not in ('containers','engine_services') or path.name=='host_checks.c':continue
        before=(source/relative).read_text();after=path.read_text()
        if before==after:continue
        normalize=lambda t:re.sub(r'#include "[^"\n]*resident(?:_v32)?/(?:resident/)?([^"\n]+)"',r'#include "RESIDENT/\1"',t)
        if normalize(before)==normalize(after):include_changes.append(str(relative))
        else:engine_changes.append(str(relative))
    assert engine_changes==['containers/product/adapter.c'],engine_changes
    v32=ROOT/'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'
    assert sha(v32)=='05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
    final=IMAGE/'local/reproduced-final-v33/candidate/SD_ROOT/ilaunch3'
    new=final if final.is_file() else IMAGE/'local/candidate-v33/candidate/SD_ROOT/ilaunch3'
    old=v32.read_bytes();body=new.read_bytes();assert len(old)==len(body)
    window=mapped(body,0x2005276c,8340);allowed=set(range(window,window+8340))
    allowed.update(range(0x16c,0x174));hooks=json.loads((LOCAL/'resident/hooks.json').read_text())
    for hook in hooks:
        off=mapped(body,int(hook['va'],16),hook['length'])
        if hook['number'] in (1,2,5,6,7,8,9):allowed.update(range(off,off+hook['length']))
        if hook['number']>=10 or hook['number'] in (3,4):
            assert body[off:off+hook['length']].hex()==hook['original_bytes']
    changed=[i for i,(a,b) in enumerate(zip(old,body)) if a!=b]
    assert all(i in allowed for i in changed)
    pins=mapped(body,0x200547f4,12);assert body[pins:pins+12]==old[pins:pins+12]
    # The complete C expander emitted entries, records, 160B bindings and
    # encoded default GXTS for each of 48 slots, including the old header fixture.
    a=(HERE/'acceptance/local/logs/expand-109.log').read_text()
    b=(HERE/'acceptance/local/logs/expand-110.log').read_text();assert a==b
    result=dict(status='PASS',resident_other_objects_byte_identical=objects,
        handwritten_and_generated_asm_equal=True,engine_behavior_changes=engine_changes,
        engine_include_relocations=include_changes,body_diff_bytes=len(changed),
        body_diff_outside_existing_window_hooks_checksum=0,H10_H37_official=True,
        firmware_update_bytes_unchanged=True,expanded_48_slot_vectors_equal=True)
    save(LOCAL/'delivery-inspection.json',result)
    # Include the final full-r8 engine in the real-byte IRQ vector census.
    machine=load_module(HERE/'machine_checks.py','r8_irq')
    raw=(ENGINE/'GXRCE.DAT').read_bytes();off,n=struct.unpack_from('>II',raw,132)
    known=machine.extract(LOCAL/'resident/build/resident.elf','rv_irq_save')[1]
    reader=machine.Elf(LOCAL/'resident/build/resident.elf');section=next(s for s in reader.sections if s['name']=='.payload')
    code=reader.content(section);start=known-section['va'];canonical=code[start:start+12]
    restore_va=reader.symbols['rv_irq_restore']['value'];restore=code[restore_va-section['va']:restore_va-section['va']+4]
    assert raw[off:off+n].count(canonical+restore)==1
    for incoming in range(65536):
        cpu=machine.IRQ(incoming);cpu.run(canonical);assert cpu.psw==incoming&0xffbf and cpu.r[0]==incoming
        cpu.run(restore);assert cpu.psw==incoming
    save(LOCAL/'r8-irq.json',dict(status='PASS',container_sha256=sha(ENGINE/'GXRCE.DAT'),vectors=65536,
        save_bytes=canonical.hex(),restore_bytes=restore.hex(),total_with_resident_suite=589824))
    print('PASS final artifact scope, 48 complete slot vectors and full-r8 IRQ vectors')


def gates():
    runs=json.loads((LOCAL/'verification/runs.json').read_text())
    assert len(runs)==11 and all(r['returncode']==0 for r in runs)
    assert json.loads((LOCAL/'entry-machine.json').read_text())['status']=='PASS'
    assert json.loads((LOCAL/'delivery-inspection.json').read_text())['status']=='PASS'
    phases={phase:json.loads((HERE/'acceptance/local'/('run-'+phase+'.json')).read_text()) for phase in PHASES}
    assert all(row['status']=='PASS' for row in phases.values())
    assert sum(row['host_runs'] for row in phases.values())==2548
    verification=json.loads((IMAGE/'local/verification/verification.json').read_text())
    assert verification['status']=='VERIFICATION_PASS',verification
    return phases


def stage():
    if (IMAGE/'local/package').exists():
        raise RuntimeError('Frozen full-r8 package: use finalize_v33.py stage for package_final')
    phases=gates();protected=load_module(HERE/'prepare.py','stage_freeze').check()
    previous=ROOT/'artifacts/v32-trial/full-r3-20261024/SD_ROOT'
    package=IMAGE/'local/package';sd=package/'SD_ROOT';sd.mkdir(parents=True,exist_ok=True)
    official=json.loads((IMAGE/'policy.json').read_text())['official']
    assert {p.name for p in previous.iterdir()}==set(official)|{'GXRCE.DAT'}
    expected={}
    for name in sorted(set(official)|{'GXRCE.DAT'}):
        source=ENGINE/name if name=='GXRCE.DAT' else IMAGE/'local/candidate-v33/candidate/SD_ROOT'/name if name=='ilaunch3' else previous/name
        shutil.copyfile(source,sd/name);expected[name]=dict(bytes=(sd/name).stat().st_size,sha256=sha(sd/name))
        if name not in ('ilaunch3','GXRCE.DAT'):assert (sd/name).read_bytes()==(previous/name).read_bytes() and sha(sd/name)==official[name]
    assert {p.name for p in sd.iterdir()}==set(expected)
    manifest=dict(status='STAGED_HOST_ONLY',independent_review='PENDING',user_flash_approval='PENDING',
        generation=110,official_siblings_byte_identical=28,protected_inputs=protected,
        camera_accessed=False,card_accessed=False,flashed=False,files=expected)
    save(package/'manifest.json',manifest)
    (package/'STAGED_HOST_ONLY').write_text('仅主机暂存。须另轮独立审查通过、用户明确同意后才可刷写。\n')
    (package/'SHA256SUMS').write_text(''.join(f'{row["sha256"]}  SD_ROOT/{name}\n' for name,row in sorted(expected.items())))
    print('PASS STAGED_HOST_ONLY: files=30 official siblings=28 host acceptance=',sum(r['host_runs'] for r in phases.values()))


def checksums(verify=False):
    for directory in (HERE,HERE/'acceptance',IMAGE):
        manifest=directory/'SHA256SUMS'
        if verify:
            for line in manifest.read_text().splitlines():
                digest,name=line.split('  ',1);assert sha(directory/name)==digest,name
        else:
            files=[p for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts]
            manifest.write_text(''.join(f'{sha(path)}  {path.relative_to(directory)}\n' for path in files))
    print('PASS delivery checksums' if verify else 'WROTE delivery checksums')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('inspect','stage','sums','check'));args=parser.parse_args()
    if args.phase=='inspect':inspect()
    elif args.phase=='stage':stage()
    elif args.phase=='sums':checksums()
    else:
        load_module(HERE/'prepare.py','check_freeze').check();gates();checksums(True)


if __name__=='__main__':main()
