"""Build all four final-format variants, waiting only at the declared load gate."""
from pathlib import Path
import datetime
import json
import os
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import build as B
C.setup();deadline=datetime.datetime.fromisoformat('2026-11-04T13:33:00+00:00').timestamp()
while os.getloadavg()[0]>10:
    assert time.time()<deadline,'deadline reached before r0 preservation'
    time.sleep(10)
if not (C.LOCAL/'stages/r0').exists():C.load(C.HERE/'preserve_r0.py','g157_preserve_r0')
assert (C.LOCAL/'stages/r0/source-freeze.json').is_file(),'incomplete r0 preservation'
rows=[]
for dataset in ('control','model'):
    C.DATASET=dataset
    for profile in ('test','release'):
        while os.getloadavg()[0]>10:
            assert time.time()<deadline,'deadline reached before all variants linked'
            time.sleep(10)
        rows.append(B.package(profile,C.artifact(profile)['records']))
        C.save(C.LOCAL/'r1-builds.json',rows)
C.save(C.LOCAL/'engine-freeze.json',dict(source_C={str(p.relative_to(C.ENGINE)):C.sha(p.read_bytes()) for p in C.ENGINE.rglob('*') if p.is_file() and p.suffix in ('.c','.h','.S','.ld') and 'local' not in p.relative_to(C.ENGINE).parts},profiles=rows))
