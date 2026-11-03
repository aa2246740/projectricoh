"""Sanitized host acceptance; native UI/files/RPC are explicit doubles."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import host_compile

FINAL=c.LOCAL/'full-r6'
OLD={105:c.ROOT/'firmware/engine_fix_r2/local/product/candidates/full-r3',
     106:c.ROOT/'firmware/full_r4/local/full-r4',107:c.ROOT/'firmware/full_r5/local/full-r5'}
RESULTS=[]


def execute(binary,scenario,unit,old=107,extra=(),tag=None):
    folder=OLD[old] if isinstance(old,int) else old
    label=tag or f'{binary}-{scenario}-{unit}-old{old if isinstance(old,int) else "fixture"}'+'-'.join(str(x) if not isinstance(x,Path) else x.name for x in extra)
    result=c.run([c.LOCAL/'host'/binary,scenario,unit,folder/'GXRCE.DAT',FINAL/'GXRCE.DAT',
        FINAL/'trust.bin',folder/'effective-rows.bin',FINAL/'effective-rows.bin',*extra],label)
    lines=result.stdout.rstrip().splitlines();assert lines[-1].startswith('OK '),label
    count=int(re.search(r'assertions=(\d+)',lines[-1])[1])
    limitation='RESIDUAL_RISK' in result.stdout or 'ACCEPTED_F02' in result.stdout
    RESULTS.append(dict(binary=binary,scenario=scenario,unit=unit,old=str(old),extra=[str(x) if isinstance(x,Path) else x for x in extra],
        status='LIMITATION_REPRODUCED' if limitation else 'PASS',assertions=count,log='local/logs/'+label+'.log',
        native28_UI_case_inapplicable='NATIVE28_PASS' in result.stdout))
    return result.stdout


def static():
    sys.path.insert(0,str(c.PRODUCT));import pack
    streams={}
    for gen,folder in list(OLD.items())+[(108,FINAL)]:
        for name in pack.NAMES:
            result=c.run([c.LOCAL/'host/validate',folder/'GXRCE.DAT',folder/'trust.bin',name],f'validate-{gen}-{name}')
            assert f'OK build={gen}' in result.stdout and 'semantic=1' in result.stdout
        raw=c.run([c.LOCAL/'host/expand',folder/'GXRCE.DAT',folder/'trust.bin'],f'expand-{gen}').stdout
        streams[gen]={(int(row[0]),int(row[1])):tuple(bytes.fromhex(x) for x in row[2:]) for row in (line.split() for line in raw.splitlines())}
        assert len(streams[gen])==48
    checks=[]
    for key,new in streams[108].items():
        old=streams[107][key];changed=key in {(0,9),(0,10)}
        if not changed:assert new==old,key
        else:
            assert new[0]==streams[108][0,4][0]
            assert new[1]==pack.v1.alias_record(key[1])
            assert new[0]!=old[0] and new[1]!=old[1] and new[2]!=old[2]
        checks.append(dict(unit=key[0],slot=key[1],changed=changed,expanded_bytes=list(map(len,new))))
    assert (FINAL/'GXRCE.DAT').read_bytes()[48:112]+(FINAL/'GXRCE.DAT').read_bytes()[212:228]==(OLD[107]/'GXRCE.DAT').read_bytes()[48:112]+(OLD[107]/'GXRCE.DAT').read_bytes()[212:228]
    # The independent, frozen complete validator sees the same final vectors.
    frozen=c.UPSTREAM/'containers/product';container=frozen/'src/firmware/card_container_v2';core=frozen/'src/firmware/engine/core'
    driver=c.LOCAL/'host/frozen-expand.c';driver.write_text(host_compile.VECTOR.replace('VALIDATOR',str(container/'validate.c')))
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
    c.run(['/usr/bin/clang',*flags,'-include',core/'eng_crc_bindings.h','-I',container,driver,
        *[container/n for n in ('gate.c','semantic.c','common.c','api.c','gxts.c')],
        c.ROOT/'firmware/resident_v32/engine_services/crc.c',frozen/'memory.c',core/'eng_crc_compat.c','-o',c.LOCAL/'host/frozen-expand'],'frozen-expand-compile')
    a=c.run([c.LOCAL/'host/frozen-expand',FINAL/'GXRCE.DAT',FINAL/'trust.bin'],'frozen-expand-108').stdout
    b=c.run([c.LOCAL/'host/expand',FINAL/'GXRCE.DAT',FINAL/'trust.bin'],'current-expand-108').stdout
    assert a==b
    c.save(c.LOCAL/'static-results.json',dict(status='PASS',validator_runs=12,expanded_slots=192,
        frozen_final_slots=48,unchanged_entry_record_binding_default_vectors=46,changed=[[0,9],[0,10]],slots=checks))


def legacy():
    predecessor=c.LOCAL/'fixture-107';predecessor.mkdir(exist_ok=True)
    sys.path.insert(0,str(c.PRODUCT));import pack
    raw=bytearray((FINAL/'GXRCE.DAT').read_bytes());pack.p32(raw,28,107)
    (predecessor/'GXRCE.DAT').write_bytes(pack.seal(raw))
    for name in ('trust.bin','effective-rows.bin'):shutil.copyfile(FINAL/name,predecessor/name)
    c.save(predecessor/'fixture.json',dict(production=False,description='Current engine/data with generation 107, host predecessor only'))
    scenarios=('flow','s-entry','badcrc','bad-layout','bad-tweak','image-limit','truncated','readfail','rename-install','rename-mark','alloc-main','alloc-work','heap-load','sd-write','unit-rpc','unit-entry','a4-save-open','a4-save-rename')
    start=len(RESULTS)
    for folder in (107,predecessor):
        for name in scenarios:
            for unit in range(3):execute('host_legacy',name,unit,folder)
    extras=['firstboot-empty','gxts-read-failure','gxts-partial-io','install-readback-failure','install-readback-mismatch','install-readback-open','gxts-readback-open','gxts-readback-mismatch','lease-preload','lease-save']
    extras += ['boundary-'+name+suffix for name in ('open','create','read','write','close','rename','delete') for suffix in ('','-neg2')]
    for name in extras:
        for unit in range(3):execute('host_legacy',name,unit)
    rev=c.load(c.ROOT/'firmware/engine_fix_r2/verify.py','inherited_r2_cases')
    for name in rev.REVISION_CASES:
        for unit in range(3):execute('host_legacy',name,unit,predecessor)
    for unit in range(3):execute('host_legacy','r3-gxts-persistent-minus1',unit,predecessor)
    c.save(c.LOCAL/'legacy-results.json',dict(status='PASS',host_runs=len(RESULTS)-start,
        cases=RESULTS[start:],note='28mm UI cases assert native behavior; persistent -1 remains a limitation'))


def historical():
    start=len(RESULTS)
    for generation in (105,106,107):
        names=['r5-update-reject','r5-update-replace','r5-conflict-pair-ok','r5-conflict-pair-empty','r5-conflict-single-ok','r5-conflict-single-empty']
        if generation==105:names+=['r5-first-reject','r5-first-replace']
        for name in names:
            for unit in range(3):
                evidence=c.LOCAL/'historical-evidence'/f'{name}-{generation}-{unit}';evidence.mkdir(parents=True,exist_ok=True)
                execute('host_checks',name,unit,generation,[evidence])
    for name in ('installed','never-run','empty','partial-a','partial-b','partial-both','old-ok','older-ab-ok','older-ab-empty','older-a-ok','older-a-empty','accepted-f02'):
        for unit in range(3):
            evidence=c.LOCAL/'review-evidence'/f'{name}-{unit}';evidence.mkdir(parents=True,exist_ok=True)
            execute('host_review',name,unit,105,[evidence])
    for name in ('repeat-old','repeat-new','all-tweaks'):
        for unit in (0,2):
            evidence=c.LOCAL/'review-evidence'/f'{name}-{unit}';evidence.mkdir(parents=True,exist_ok=True)
            execute('host_review',name,unit,105,[evidence])
    c.save(c.LOCAL/'historical-results.json',dict(status='PASS',host_runs=len(RESULTS)-start,cases=RESULTS[start:]))


def behavior():
    start=len(RESULTS)
    for policy in (0,1):
        execute('host_v33','per-unit',0,extra=[policy])
        for unit in range(3):
            execute('host_v33','visible',unit,extra=[policy])
            for copies in ('one','both'):execute('host_v33','direct-stale-'+copies,unit,extra=[policy])
        for unit in (0,2):
            for name in ('auto-apply-failure','manual-apply-failure'):execute('host_v33',name,unit,extra=[policy])
            for name in ('remember05','remember03','remember-corrupt','remember-stale','remember-missing','remember-unreadable','remember-hidden09','remember-hidden10','invalid-row-0','invalid-row-9','invalid-row-16'):
                execute('host_v33',name,unit,extra=[policy])
            for name in ('stale-one','stale-both','stale-slot2-one','stale-slot2-both'):
                execute('host_v33',name,unit,105,[policy])
        for gen in (105,106,107):
            for unit in range(3):
                for name in ('upgrade-empty','upgrade-saved'):execute('host_v33',name,unit,gen,[policy])
    c.save(c.LOCAL/'behavior-results.json',dict(status='PASS',host_runs=len(RESULTS)-start,cases=RESULTS[start:]))


def faults():
    start=len(RESULTS);injections=0;traces=[]
    for kind in ('tweak','last'):
        for initial in (0,1,2):
            trace=execute('host_v33','trace-'+kind,0,extra=[1,initial])
            counts={int(op):int(n) for op,n in re.findall(r'op(\d+)=(\d+)',trace)}
            assert all(counts[op]>0 for op in (2,3,4,5,6,7))
            if initial:assert counts[8]>0
            traces.append(dict(kind=kind,initial=initial,counts=counts))
            for unit in (0,2):
                for policy in (0,1):
                    for op in (2,3,4,5,6,7,8):
                        for ordinal in range(1,counts[op]+1):
                            for code in (-1,-2):
                                execute('host_v33','fault-'+kind,unit,extra=[policy,initial,op,ordinal,code]);injections+=1
    c.save(c.LOCAL/'fault-results.json',dict(status='PASS',host_runs=len(RESULTS)-start,injections=injections,traces=traces,cases=RESULTS[start:]))


def additional():
    source=(c.HERE/'host_v33.c').read_text()
    assert source.count('int main(int argc,char **argv)')==1
    c.write(c.LOCAL/'additional_support.c',source.replace('int main(int argc,char **argv)','int v33_fixture_main(int argc,char **argv)').encode())
    calls=[json.loads(line) for line in (c.LOCAL/'commands.jsonl').read_text().splitlines()]
    cmd=next(r['argv'] for r in reversed(calls) if re.fullmatch(r'host-compile-\d+',r['label']) and str(c.HERE/'host.c') in r['argv'])
    old_object=cmd[cmd.index('-o')+1];obj=c.LOCAL/'host/host_additional.o'
    cmd=[str(c.HERE/'host_additional.c') if a==str(c.HERE/'host.c') else str(obj) if a==old_object else a for a in cmd]
    cmd=cmd[:1]+['-I',str(c.HERE)]+cmd[1:]
    c.run(cmd,'host-additional-compile')
    cmd=next(r['argv'] for r in reversed(calls) if r['label']=='host-link');assert cmd.count(old_object)==1
    cmd=[str(obj) if a==old_object else a for a in cmd];cmd[cmd.index('-o')+1]=str(c.LOCAL/'host/host_additional')
    c.run(cmd,'host-additional-link')
    for policy in (0,1):
        for unit in range(3):
            for name in ('partial-both','direct-repeat'):execute('host_additional',name,unit,extra=[policy])
        for unit in (0,2):
            for name in ('last-pair-one','last-pair-both'):execute('host_additional',name,unit,extra=[policy])
    c.save(c.LOCAL/'additional-results.json',dict(status='PASS',host_runs=len(RESULTS),cases=RESULTS))


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['compile','drivers','static','legacy','historical','behavior','faults','additional']);args=p.parse_args()
    c.guard();c.freeze_check()
    if args.phase=='compile':
        sys.path.insert(0,str(c.PRODUCT));import build
        host_compile.compile_all(build)
    elif args.phase=='drivers':host_compile.compile_drivers()
    else:globals()[args.phase]()
    c.freeze_check()
    print(json.dumps(dict(status='PASS',phase=args.phase,host_runs=len(RESULTS),assertions=sum(r['assertions'] for r in RESULTS))))


if __name__=='__main__':main()
