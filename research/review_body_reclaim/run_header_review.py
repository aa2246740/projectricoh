#!/usr/bin/python3
"""Build only the header functions; run the supplied and extended host cases."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/header'
OUT.mkdir(exist_ok=True)
for name,variant in [('old','vS1'),('new','r3')]:
    text=(HERE/f'local/rebuild/v/{variant}/validate_envelope.inc.c').read_text()
    begin=text.index('GxrceStatus rv_header(');index=text.index('{',begin);depth=0
    while True:
        c=text[index];depth+=(c=='{')-(c=='}');index+=1
        if not depth:break
    (OUT/f'{name}_header.inc').write_text(text[begin:index]+'\n')
flags=['-std=c11','-O1','-g','-Wall','-Wextra','-fsanitize=address,undefined',
       '-fno-omit-frame-pointer','-DRV_HOST',f'-I{HERE}/local/rebuild/v/r3',
       f'-DOLD_SRC="{OUT}/old_header.inc"',f'-DNEW_SRC="{OUT}/new_header.inc"',
       f'-DORIGINAL_EQUIV="{ROOT}/research/body_next_steps/prototype/equiv/header_equiv.c"']
records=[]
for tag,args in [('compile',['/usr/bin/clang',*flags,HERE/'header_boundaries.c','-o',OUT/'header-review']),
                 ('run',[OUT/'header-review'])]:
    start=time.monotonic()
    with (OUT/f'{tag}.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/nice','-n','10',*map(str,args)],stdout=stream,
                              stderr=subprocess.STDOUT,timeout=900,env=os.environ.copy())
    records.append({'step':tag,'returncode':result.returncode,'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':900})
    if result.returncode:
        print((OUT/f'{tag}.log').read_text());raise SystemExit(result.returncode)
rows=[json.loads(line) for line in (OUT/'run.log').read_text().splitlines()]
(HERE/'local/header-result.json').write_text(json.dumps({'records':records,'results':rows},indent=2)+'\n')
print(json.dumps({'records':records,'results':rows},indent=2))
