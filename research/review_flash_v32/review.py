#!/usr/bin/env python3
"""Rerun this read-only review; every generated artifact stays in this task."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
PYTHON='/usr/bin/python3'


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name,value):
    (LOCAL/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def protected_inputs():
    inputs=json.loads((LOCAL/'inputs-before.json').read_text())
    changes=[];frozen_changes=[]
    for name,record in inputs.items():
        if not (ROOT/name).is_file() or sha(ROOT/name)!=record['sha256']:changes.append(name)
        if '/prefix/' not in name:
            copy=LOCAL/'frozen'/name
            if not copy.is_file() or sha(copy)!=record['sha256']:frozen_changes.append(name)
    assert not changes and not frozen_changes,(changes,frozen_changes)
    return len(inputs)


def validate_results():
    required=('image-independent.json','v31-v32-image.json','regression/results.json',
              'extra-host-results.json','policy-machine/results.json','containers-independent.json',
              'full-checks/results.json','stack-increment.json','all-objdump-bytes.json',
              'irq-machine.json','irq-pairs-machine.json','replay-machine.json','h07-machine.json')
    results={n:json.loads((LOCAL/n).read_text()) for n in required}
    assert all(v['status']=='PASS' for v in results.values())
    assert len(json.loads((LOCAL/'product-results.json').read_text()))==60
    assert results['policy-machine/results.json']['H09']['packet_cases']==66379
    assert len(results['policy-machine/results.json']['F08'])==21
    assert len(results['policy-machine/results.json']['H07'])==64
    assert len(results['containers-independent.json']['full_C_validations'])==18
    assert results['all-objdump-bytes.json']['disassembly_files']==59
    consumed=json.loads((LOCAL/'consumed-independent.json').read_text())
    assert consumed['default_vectors']==896 and consumed['consumed_vectors']==640
    refs=json.loads((LOCAL/'xrefs.json').read_text())
    assert all(not row['inner'] for name in ('direct','pointers','constructed','encoding_candidates') for row in refs[name])
    tables=json.loads((LOCAL/'relative-tables-summary.json').read_text());assert not tables['inner_hits']
    assert (LOCAL/'image-v3-audit.log').read_text().startswith('AUDIT_PASS_UNREVIEWED ')
    return required


def finalize():
    r=module(LOCAL/'inspect.py','review_preflight');r.preflight()
    count=protected_inputs();required=validate_results()
    status=subprocess.check_output(['git','-c','core.fsmonitor=false','--no-optional-locks',
                                    'status','--short','--untracked-files=no'],cwd=ROOT,text=True)
    (LOCAL/'git-status-final.txt').write_text(status)
    assert status==(LOCAL/'git-status-initial.txt').read_text()
    ignore=subprocess.check_output(['git','check-ignore','-v','research/review_flash_v32/local/check'],cwd=ROOT,text=True)
    (LOCAL/'ignore-final.log').write_text(ignore)
    report=(HERE/'REPORT.md').read_text();assert report.splitlines()[0]=='可以刷'
    image=LOCAL/'frozen/firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'
    assert sha(image)=='05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
    assert sha(image) in report
    broken=[];links=re.findall(r'\]\(([^)]+)\)',report)
    for target in links:
        if target.startswith(('http:','https:','#')):continue
        name=re.sub(r':\d+$','',target.split('#',1)[0])
        if name=='SHA256SUMS':continue
        if name=='local/delivery-validation.json':continue
        if not (HERE/name).exists():broken.append(target)
    assert not broken,broken
    assert all(not p.is_symlink() for p in HERE.rglob('*'))
    save('delivery-validation.json',dict(status='PASS',protected_inputs=count,changed_inputs=[],
        frozen_inputs_unchanged=True,git_tracked_status_matches_initial=True,
        report_links_checked=len(links),broken_links=[],local_ignored=ignore.strip(),
        outputs_scope='research/review_flash_v32/',camera_accessed=False,sd_accessed=False,
        firmware_built=False,source_modified=False,subagents_started=False,
        sleep_or_periodic_polling=False,commit_or_push=False,checks=list(required),
        limits='Final artifact bytes and host models/doubles. Physical format, camera behavior and whole-task stack peak are not observed.'))
    # This record is covered by the final manifest; the manifest excludes itself.
    files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and p!=LOCAL/'checksums-verification.json']
    save('checksums-verification.json',dict(status='PASS',listed_files=len(files)+1,algorithm='SHA-256',
                                         manifest_excludes_itself=True))
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and p!=HERE/'SHA256SUMS')
    (HERE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(HERE).as_posix()+'\n' for p in files))
    verify()
    print('FINALIZE_PASS protected_inputs=%d report_links=%d manifest_sha256=%s'%(count,len(links),sha(HERE/'SHA256SUMS')))


def verify():
    entries={}
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest,sep,name=line.partition('  ');assert sep and re.fullmatch('[0-9a-f]{64}',digest)
        assert name not in entries and (HERE/name).resolve().is_relative_to(HERE)
        entries[name]=digest;assert (HERE/name).is_file() and sha(HERE/name)==digest,name
    actual={p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and p!=HERE/'SHA256SUMS'}
    assert set(entries)==actual
    count=protected_inputs()
    print('SHA256SUMS_PASS files=%d protected_inputs=%d'%(len(entries),count))


def run_all():
    r=module(LOCAL/'inspect.py','review_preflight');r.preflight();protected_inputs()
    env=dict(os.environ,TMPDIR=str(LOCAL/'tmp'),ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
             UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    stages=[('collect',['inspect.py','collect']),('extra-disasm',['extra_disasm.py']),
            ('image',['image_checks.py']),('regression',['regression_checks.py']),
            ('extra-host',['extra_host_checks.py']),('machine',['machine_checks.py']),
            ('consumed',['consumed_checks.py']),('policy',['policy_checks.py']),
            ('product',['product_checks.py']),('full',['full_checks.py']),
            ('container',['container_checks.py']),('stack',['stack_checks.py']),
            ('summary',['summary_checks.py']),('xrefs',['inspect.py','xrefs'])]
    for name,args in stages:
        print('RUN '+name,flush=True)
        command=[PYTHON,'-I','-B',str(LOCAL/args[0]),*args[1:]]
        p=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
        (LOCAL/(name+'-rerun.log')).write_text(p.stdout+p.stderr)
        if p.returncode:
            failure=LOCAL/'failures'/(name+'-rerun-'+hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest()[:12]+'.log')
            failure.write_text(p.stdout+p.stderr)
            raise SystemExit('%s failed: %s'%(name,failure))
    command=[PYTHON,'-I','-B',str(ROOT/'firmware/image_v3/audit.py'),
             '--package',str(ROOT/'firmware/image_v3/local/candidate-v32'),
             '--official',str(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'),
             '--elf',str(ROOT/'firmware/resident_v32/local/resident/build/resident.elf'),
             '--hooks',str(ROOT/'firmware/resident_v32/local/hooks.json'),
             '--patch-manifest',str(ROOT/'firmware/resident_v32/local/patch-manifest.json')]
    p=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
    (LOCAL/'image-v3-audit.log').write_text(p.stdout+p.stderr);assert not p.returncode
    finalize()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--verify',action='store_true')
    group.add_argument('--finalize',action='store_true')
    args=parser.parse_args()
    if args.verify:verify()
    elif args.finalize:finalize()
    else:run_all()
