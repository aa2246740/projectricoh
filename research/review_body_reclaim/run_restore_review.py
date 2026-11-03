#!/usr/bin/python3
"""Run the same K-field failure cases against r3 and r4 source copies."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
OUT=HERE/'local/restore'
OUT.mkdir(exist_ok=True)
records=[];rows={}
for variant in ['r3','r4']:
    source=HERE/'local/rebuild/v'/variant
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Wno-unknown-attributes',
           '-fno-builtin','-fsanitize=address,undefined','-fno-omit-frame-pointer',
           '-DRV_HOST','-DREVIEW_C5=1',f'-I{source}',f'-I{HERE}/local/host']
    units=[HERE/'restore_review.c',source/'resident.c',source/'shared.c',source/'hooks.c',
           source/'loader.c',source/'validate_envelope.inc.c',HERE/'local/host/services.c',HERE/'local/host/api.c']
    for step,args in [('compile',['/usr/bin/clang',*flags,*units,'-o',OUT/variant]),('run',[OUT/variant])]:
        start=time.monotonic()
        with (OUT/f'{variant}-{step}.log').open('w') as stream:
            result=subprocess.run(['/usr/bin/nice','-n','10',*map(str,args)],stdout=stream,
                                  stderr=subprocess.STDOUT,timeout=600,env=os.environ.copy())
        records.append({'variant':variant,'step':step,'returncode':result.returncode,
                        'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':600})
        if result.returncode:
            print((OUT/f'{variant}-{step}.log').read_text());raise SystemExit(result.returncode)
    rows[variant]=[json.loads(line) for line in (OUT/f'{variant}-run.log').read_text().splitlines()]
result={'classification':'actual image_hook C with K-field writes in a declared DAT substitute',
        'records':records,'cases':rows,
        'manual_capability_setup':'CAP_BODY set only in the review fixture to get past the separately reported publication defect.'}
(HERE/'local/restore-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'records':records,'cases_per_variant':len(rows['r3']),
                  'unmarked_restoration':{v:[hex(x['offset']) for x in entries if not x['marked'] and x['restored']] for v,entries in rows.items()}},indent=2))
