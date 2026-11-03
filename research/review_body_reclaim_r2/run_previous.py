#!/usr/bin/python3
"""Repeat previous counterexamples, retaining old DAT semantics for r3."""
import json, os, shutil, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-reclaim-r2')
OUT=HERE/'local/previous'
OUT.mkdir(exist_ok=True)
records=[]
fixture=(HERE/'previous_host.c').read_text()
for variant in ['vS1','r3','r7']:
    source=HERE/'local/rebuild/v'/variant
    work=TEMP/('previous-'+variant)
    work.mkdir(exist_ok=True)
    services=ROOT/'firmware/resident_v38/engine_services'
    for name in ['services.c','api.c','engine_services.h']:
        text=(services/name).read_text().replace('r->grain=0;','').replace('#include "../resident/resident.h"','#include "resident.h"')
        (work/name).write_text(text)
    code=fixture
    if variant=='r7':
        old='p->actual=next_mode==6?39:40;'
        assert code.count(old)==1
        code=code.replace(old,old+'\n        p->detail=next_mode==14?0:RV_INIT_DONE;')
    unit=work/'host.c';unit.write_text(code)
    binary=work/'host'
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unknown-attributes','-fno-builtin',
           '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
           '-DRV_HOST',f'-DREVIEW_C5={int(variant=="r3")}',f'-I{source}',f'-I{work}']
    args=['/usr/bin/clang',*flags,unit,*[source/n for n in ['resident.c','shared.c','hooks.c','loader.c','validate_envelope.inc.c']],
          work/'services.c',work/'api.c','-o',binary]
    groups=['epoch']+(['image'] if variant!='vS1' else [])
    for name,argv in [('compile',args),*[(g,[binary,g]) for g in groups]]:
        start=time.monotonic();log=OUT/f'{variant}-{name}.log'
        with log.open('w') as stream:p=subprocess.run(['/usr/bin/nice','-n','10',*map(str,argv)],stdout=stream,stderr=subprocess.STDOUT,timeout=600,env=os.environ.copy())
        records.append(dict(variant=variant,group=name,returncode=p.returncode,elapsed_seconds=round(time.monotonic()-start,3),timeout_seconds=600))
        if p.returncode:print(log.read_text()[-5000:]);raise SystemExit(p.returncode)
def rows(v,g):return [json.loads(line) for line in (OUT/f'{v}-{g}.log').read_text().splitlines()]
for v in ['vS1','r7']:
    assert all(r['native_writes']==0 and r['service_result']==-5 for r in rows(v,'epoch'))
assert [r['native_writes'] for r in rows('r3','epoch')]==[1,1,0,0,1,1]
assert rows('r3','image')[0]['dat_calls']==0 and rows('r7','image')[0]['dat_calls']==1
assert rows('r3','image')[-1]['arg13']==0 and rows('r7','image')[-1]['arg13']==0x87654321
result=dict(records=records,epochs={v:rows(v,'epoch') for v in ['vS1','r3','r7']},image={v:rows(v,'image') for v in ['r3','r7']},
            r7_fixture_change='The handshake substitute emits RV_INIT_DONE after completed_init; otherwise the prior counterexample fixture is unchanged.')
(HERE/'local/previous-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
