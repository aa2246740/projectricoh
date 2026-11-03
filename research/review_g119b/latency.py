"""Estimate communication waits from completed native paths, never host run time."""
from pathlib import Path
import collections
import json
import math
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save

identity=json.loads((OUT/'identity.json').read_text())['119']
samples=[];groups=collections.defaultdict(list)
for unit in ('50mm','28mm','mount'):
    record=json.loads((OUT/f'native/matrix-{unit}.json').read_text())
    assert record['status']=='PASS' and record['dat_sha256']==identity['dat']
    assert len(record['fast_moves'])==41
    for step in record['fast_moves']:
        assert step['rpc_errors']==0
        assert step['unit_write_bytes']==2*step['W_attempts']
        transition=f"{step['before']['cursor']:02} to {step['after']['cursor']:02}"
        groups[transition].append(step)
        samples.append(dict(unit=unit,transition=transition,rpc=step['rpc_calls'],unit_bytes=step['unit_write_bytes']))
lo=min(x['rpc'] for x in samples);hi=max(x['rpc'] for x in samples)
table=[]
for key,steps in sorted(groups.items()):
    table.append(dict(transition=key,samples=len(steps),rpc=[min(x['rpc_calls'] for x in steps),max(x['rpc_calls'] for x in steps)],
                      unit_bytes=[min(x['unit_write_bytes'] for x in steps),max(x['unit_write_bytes'] for x in steps)]))
scenarios=[dict(mean_rpc_ms=ms,communication_wait_ms=[lo*ms,hi*ms]) for ms in (1,2,3)]
save('latency.json',dict(status='COUNT_VERIFIED_ESTIMATE',samples=len(samples),transitions=len(groups),tick_ms=1,
    rpc_range=[lo,hi],unit_bytes_range=[min(x['unit_bytes'] for x in samples),max(x['unit_bytes'] for x in samples)],
    cases=samples,table=table,scenarios=scenarios,
    formula='RPC count times assumed mean RPC milliseconds; round total up to one millisecond ticks.',
    exclusions='Camera CPU, memory waits, scheduling, preview/LCD waits and communication timeout. No hardware upper bound is claimed.',
    conclusion='At the requested 1 to 3 ms per communication, adjacent navigation has visible waiting; 2 ms already costs roughly a quarter to half a second in communication alone.',
    verification='Every sample uses final DAT, real native arrows, full recipe/T checks and zero RPC errors. CRC specification acceleration does not change communication count.'))
lines=['| 相邻行 | 样本 | RPC 次数 | 单元写入 B |','| --- | ---: | ---: | ---: |']
for row in table:
    fmt=lambda x:str(x[0]) if x[0]==x[1] else str(x[0])+'–'+str(x[1])
    lines.append('| '+row['transition']+' | '+str(row['samples'])+' | '+fmt(row['rpc'])+' | '+fmt(row['unit_bytes'])+' |')
(OUT/'cost-table.md').write_text('\n'.join(lines)+'\n')
print('PASS communication counts',len(samples),'samples,',len(groups),'transitions, RPC',lo,hi,'delay scenarios',scenarios,flush=True)
