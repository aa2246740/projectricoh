#!/usr/bin/python3
"""Compile and run one review workload at a time with explicit time limits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/host'
OUT.mkdir(exist_ok=True)

def run(args, log, timeout=600):
    start=time.monotonic()
    if log.exists():
        suffix=1
        while log.with_name(log.stem+f'-prior-{suffix}'+log.suffix).exists():
            suffix+=1
        log.rename(log.with_name(log.stem+f'-prior-{suffix}'+log.suffix))
    with log.open('w') as stream:
        result=subprocess.run(['/usr/bin/nice','-n','10',*map(str,args)],
            stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,env=os.environ.copy())
    metadata={'arguments':list(map(str,args)),'returncode':result.returncode,
              'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':timeout,
              'log':str(log.relative_to(HERE))}
    if result.returncode:
        print(log.read_text()[-5000:])
        raise RuntimeError(metadata)
    return metadata

services=ROOT/'firmware/resident_v38/engine_services'
(OUT/'services.c').write_text((services/'services.c').read_text().replace('r->grain=0;',''))
(OUT/'api.c').write_bytes((services/'api.c').read_bytes())
(OUT/'engine_services.h').write_text((services/'engine_services.h').read_text().replace(
    '#include "../resident/resident.h"','#include "resident.h"'))
records=[]
for variant in ['vS1','r3']:
    source=HERE/'local/rebuild/v'/variant
    binary=OUT/f'host-{variant}'
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unknown-attributes',
           '-fno-builtin','-fsanitize=address,undefined','-fno-omit-frame-pointer',
           '-DRV_HOST',f'-DREVIEW_C5={int(variant=="r3")}',f'-I{source}',f'-I{OUT}']
    units=[HERE/'host_review.c',source/'resident.c',source/'shared.c',source/'hooks.c',
           source/'loader.c',source/'validate_envelope.inc.c',OUT/'services.c',OUT/'api.c']
    records.append(run(['/usr/bin/clang',*flags,*units,'-o',binary],OUT/f'compile-{variant}.log'))
    groups=['check','epoch']+(['loader','image'] if variant=='r3' else [])
    for group in groups:
        records.append(run([binary,group],OUT/f'{variant}-{group}.jsonl'))

def rows(variant,group):
    return [json.loads(line) for line in (OUT/f'{variant}-{group}.jsonl').read_text().splitlines()]
old=rows('vS1','check');new=rows('r3','check')
old_snap=[x for x in old if x['case']=='check_snapshot']
new_snap=[x for x in new if x['case']=='check_snapshot']
assert len(old_snap)==len(new_snap)==36
assert all(a['rejected']==b['rejected'] for a,b in zip(old_snap,new_snap))
summary={
 'classification':'actual resident and service C with host memory and native-call substitutes',
 'snapshot_cases':36,'snapshot_rejection_mismatches':0,
 'diagnostic_changes':[{'index':a['index'],'old':a['reason'],'new':b['reason']}
                       for a,b in zip(old_snap,new_snap) if a['reason']!=b['reason']],
 'temporal_read_cases':{'vS1':old[-2:],'r3':new[-2:]},
 'epoch_cases':{'vS1':rows('vS1','epoch'),'r3':rows('r3','epoch')},
 'loader':rows('r3','loader'),'image':rows('r3','image'),
 'commands':records,
 'source_sha256':{'services.c':hashlib.sha256((OUT/'services.c').read_bytes()).hexdigest()},
 'service_adaptation':'Remove three writes to retired byte 7, as required by PLAN section 3.3; all tested service predicates are unchanged.',
 'limitations':['The DAT body is a declared substitute, not a paired production DAT.',
                'Epoch changes are injected at rv_irq_restore; physical scheduling is not established.',
                'ASan and UBSan do not establish camera, RTOS, storage, or flash acceptance.']
}
(HERE/'local/host-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['commands','source_sha256','limitations']},ensure_ascii=False,indent=2))
