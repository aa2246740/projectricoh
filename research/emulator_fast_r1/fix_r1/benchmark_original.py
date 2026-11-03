"""Alternate original batch sources and native sources in fresh processes."""
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUNS=HERE/'runs'
signal.alarm(1700)
assert os.getpriority(os.PRIO_PROCESS,0)>=10
result={'pairs':[],'status':'RUNNING','steps':10000000,'load_before':os.getloadavg(),
        'baseline':'original tools/gxr_emulator_batch','native':'tools/gxr_emulator_fast',
        'nice':os.getpriority(os.PRIO_PROCESS,0)}
target=RUNS/'benchmark-original-01.json'
assert not target.exists()
for index in range(5):
    order=('original','native') if index%2==0 else ('native','original')
    pair={'order':order,'records':{}}
    for backend in order:
        name='benchmark-original-01-'+str(index+1)+'-'+backend
        if backend=='original':
            argv=[sys.executable,'-I','-B',str(HERE/'original_reference.py'),'--name',name]
        else:
            argv=[sys.executable,'-I','-B',str(HERE/'review_runner.py'),'--backend','native',
                  '--kind','main','--name',name,'--points','10000000','--timeout','450']
        start=time.perf_counter()
        with (RUNS/(name+'.log')).open('x') as log:
            child=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=450)
        assert child.returncode==0,(name,child.returncode)
        record=json.loads((RUNS/(name+'.json')).read_text())
        if backend=='original':
            state=record['state']
            seconds=record['seconds']
            cpu_seconds=record['cpu_seconds']
            assert record['stop']['reason']=='max_steps' and record['steps']==10000000
        else:
            assert record['status']=='COMPLETE'
            state=record['points']['10000000']
            segment=record['segments'][0]
            seconds=segment['seconds']
            cpu_seconds=segment['cpu_seconds']
            assert record['native']['instructions']==10000000
            assert record['native']['python_bus_calls']==0 and not record['native']['hle_callbacks']
        pair['records'][backend]={'receipt':name+'.json','seconds':seconds,'cpu_seconds':cpu_seconds,
                                  'process_seconds':time.perf_counter()-start,'state':state,
                                  'library_sha256':record['library_sha256']}
        print(json.dumps({'pair':index+1,'backend':backend,'seconds':seconds,'cpu_seconds':cpu_seconds}),flush=True)
    assert pair['records']['original']['state']==pair['records']['native']['state']
    pair['same_state']=True
    pair['speedup']=pair['records']['original']['seconds']/pair['records']['native']['seconds']
    result['pairs'].append(pair)
    target.write_text(json.dumps(result,indent=2)+'\n')
result['summary']={}
for backend in ('original','native'):
    times=[pair['records'][backend]['seconds'] for pair in result['pairs']]
    result['summary'][backend]={'median':statistics.median(times),'minimum':min(times),'maximum':max(times),'seconds':times}
result['speedup']=result['summary']['original']['median']/result['summary']['native']['median']
result['paired_speedups']=[pair['speedup'] for pair in result['pairs']]
result['load_after']=os.getloadavg()
result['status']='COMPLETE'
target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'speedup':result['speedup'],'summary':result['summary']}),flush=True)
