"""Calculate communication waits and check recorded file counters."""
from pathlib import Path
from collections import defaultdict
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, DAT_SHA, save

def read(name):
    path=OUT/name
    return json.loads(path.read_text()) if path.exists() else None

def latency():
    moves=[]
    failures=[]
    fn2=[]
    for unit in ('50mm','28mm','mount'):
        value=read('native/matrix-'+unit+'.json')
        if value and value.get('status')=='PASS':
            assert value['dat_sha256']==DAT_SHA and len(value['fast_moves'])==41
            for step in value['fast_moves']:
                assert step['rpc_errors']==0
                moves.append(dict(unit=unit,source=step['before']['cursor'],target=step['after']['cursor'],
                                  RPC=step['rpc_calls'],W=step['W_attempts'],write_bytes=step['unit_write_bytes']))
            for label,step in [('cold_compensation',value['cold_failure']['step']),
                               ('fallback04',value['fallback04']['step'])]+[
                               ('compensation_'+str(i+1),row['step']) for i,row in enumerate(value['faults'])]:
                failures.append(dict(operation='list',unit=unit,label=label,RPC=step['rpc_calls']))
        value=read('native/fn2-step-counts-'+unit+'.json')
        if value and value.get('status')=='PASS':
            assert value['dat']==DAT_SHA
            for row in value['steps']:
                fn2.append(dict(unit=unit,parameter=row['parameter'],label=row['label'],
                                RPC=row['RPC'],W=row['W'],write_bytes=row['write_bytes']))
        value=read('native/fn2-failures-'+unit+'.json')
        if value and value.get('status')=='PASS':
            for row in value['cases']:
                failures.append(dict(operation='fn2',unit=unit,label=row['label'],
                                     RPC=row['after']['rpc']-row['before']['rpc']))
    def summarize(rows):
        if not rows:return None
        counts=[row['RPC'] for row in rows]
        return dict(samples=len(rows),RPC=[min(counts),max(counts)],
                    wait_ms={str(ms):[min(counts)*ms,max(counts)*ms] for ms in (1,2,3)},
                    over_300={str(ms):sum(value*ms>300 for value in counts) for ms in (1,2,3)})
    by_transition=defaultdict(list)
    for row in moves:by_transition[(row['source'],row['target'])].append(row)
    by_parameter={str(i):summarize([row for row in fn2 if row['parameter']==i]) for i in range(1,5)}
    value=dict(status='COMPLETE' if len(moves)==123 and len(fn2)==240 else 'INCOMPLETE',
               dat_sha256=DAT_SHA,tick_ms=1,list_move=summarize(moves),fn2=by_parameter,
               failures={label:summarize([row for row in failures if row['operation']+'_'+row['label']==label])
                         for label in sorted({row['operation']+'_'+row['label'] for row in failures})},
               transitions=[dict(source=a,target=b,**summarize(rows)) for (a,b),rows in sorted(by_transition.items())],
               assumptions='Wait equals RPC count times assumed 1, 2 or 3 ms per call, rounded to 1 ms ticks. CPU, display, scheduler and failure timeouts are excluded. Fn2 counts cover recipe 05 only.',
               list_samples=moves,fn2_samples=fn2)
    save('latency.json',value)
    lines=['source\ttarget\tsamples\tRPC_min\tRPC_max\twait_1ms_min\twait_1ms_max\twait_2ms_min\twait_2ms_max\twait_3ms_min\twait_3ms_max\tover_300_at_2ms\tover_300_at_3ms']
    for row in value['transitions']:
        columns=[row['source'],row['target'],row['samples'],*row['RPC'],
                 *row['wait_ms']['1'],*row['wait_ms']['2'],*row['wait_ms']['3'],
                 row['over_300']['2'],row['over_300']['3']]
        lines.append('\t'.join(map(str,columns)))
    (OUT/'latency-transitions.tsv').write_text('\n'.join(lines)+'\n')
    return value

def file_counters():
    rows=[]
    failures=[]
    def visit(value,path):
        if isinstance(value,dict):
            required={'create','write','rename','delete','write_open'}
            if required<=set(value):
                rows.append(path)
                if any(value[key]!=0 for key in required):failures.append(dict(file=path,counts=value))
            for nested in value.values():visit(nested,path)
        elif isinstance(value,list):
            for nested in value:visit(nested,path)
    for path in sorted((OUT/'native').rglob('*.json')):
        visit(json.loads(path.read_text()),str(path.relative_to(OUT)))
    for name in ('machine-gates.json',):
        value=read(name)
        if value:visit(value,name)
    assert not failures,failures
    save('zero-file-write-audit.json',dict(status='PASS',observations=len(rows),
        records=len(set(rows)),failures=failures,scope='Recorded file counters only; static capability evidence is separate.'))

if __name__=='__main__':
    value=latency()
    file_counters()
    print('PASS result calculations',value['status'],flush=True)
