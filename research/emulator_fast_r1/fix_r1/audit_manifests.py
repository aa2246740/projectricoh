"""Read-only verification of supplied checksums and historical input identity."""
from pathlib import Path
import hashlib
import json
import os
import signal
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
signal.alarm(1700)
assert os.getpriority(os.PRIO_PROCESS,0)>=10
began=time.perf_counter()
memo={}
result={'manifests':{},'unique_bytes':0}
for name in ('research/emulator_fast_r1/SHA256SUMS','tools/gxr_emulator_fast/SHA256SUMS'):
    raw=(ROOT/name).read_bytes()
    rows=raw.decode().splitlines()
    record={'manifest_sha256':hashlib.sha256(raw).hexdigest(),'count':len(rows),'mismatches':[],'missing':[]}
    for line in rows:
        expected,relative=line.split(None,1)
        relative=relative.lstrip('*')
        path=(ROOT/relative).resolve()
        assert path.is_relative_to(ROOT) and not str(path).startswith('/Volumes/RICOH')
        if not path.is_file():
            record['missing'].append(relative)
            continue
        if path not in memo:
            h=hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda:f.read(2**20),b''):
                    h.update(block)
            memo[path]=h.hexdigest()
            result['unique_bytes']+=path.stat().st_size
        if memo[path]!=expected:
            record['mismatches'].append({'path':relative,'expected':expected,'actual':memo[path]})
    result['manifests'][name]=record
    result['seconds']=time.perf_counter()-began
    (HERE/'runs/supplied-manifests.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'manifest':name,'count':record['count'],'mismatches':len(record['mismatches']),
                      'missing':len(record['missing']),'seconds':result['seconds']}),flush=True)
result['unique_files']=len(memo)
result['status']='PASS' if all(not v['missing'] and not v['mismatches'] for v in result['manifests'].values()) else 'FAIL'
(HERE/'runs/supplied-manifests.json').write_text(json.dumps(result,indent=2)+'\n')
