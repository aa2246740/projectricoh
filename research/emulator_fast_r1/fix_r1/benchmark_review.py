"""Five alternating fresh-machine pairs. Timing includes native state sync."""
import argparse
import gc
import json
import os
from pathlib import Path
import signal
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review_runner as R
STEPS=10000000


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='benchmark-01')
    args=parser.parse_args()
    signal.alarm(1700)
    result={'claim':'MAIN cold execution speed, 10000000 instructions, same full state',
            'pairs':[],'status':'RUNNING','pid':os.getpid(),'nice':os.getpriority(os.PRIO_PROCESS,0),
            'load_before':os.getloadavg(),'python':sys.version}
    target=R.RUNS/(args.name+'.json')
    assert not target.exists()
    for index in range(5):
        order=('reference','native') if index%2==0 else ('native','reference')
        pair={'order':order,'records':{}}
        for backend in order:
            R.setup(backend)
            began=time.perf_counter()
            ctx=R.construct('main','bench-'+str(index)+'-'+backend)
            m,c=ctx.machine,ctx.machine.cpu
            setup_seconds=time.perf_counter()-began
            loads=os.getloadavg()
            wall=time.perf_counter()
            cpu=time.process_time()
            stop=c.run(STEPS)
            c.materialize_native()
            seconds=time.perf_counter()-wall
            cpu_seconds=time.process_time()-cpu
            assert stop.reason=='max_steps' and c.steps==STEPS
            fp=R.fingerprint(ctx)
            record={'seconds':seconds,'cpu_seconds':cpu_seconds,'setup_seconds':setup_seconds,
                    'load_before':loads,'load_after':os.getloadavg(),'steps':c.steps,'stop':stop.to_dict(),
                    'fingerprint':fp,'native':c._native_driver.stats() if c._native_driver else None,
                    'library_sha256':R.sha(c.library_path.read_bytes()),'inputs':ctx.inputs.captured,
                    'batch_stats':dict(c.batch_stats)}
            if backend=='native':
                assert record['native']['instructions']==STEPS
                assert record['native']['python_bus_calls']==0 and not record['native']['hle_callbacks']
            pair['records'][backend]=record
            m.close()
            del ctx,m,c
            gc.collect()
            print(json.dumps({'pair':index+1,'backend':backend,'seconds':seconds,'cpu_seconds':cpu_seconds}),flush=True)
        assert pair['records']['native']['fingerprint']==pair['records']['reference']['fingerprint']
        pair['speedup']=pair['records']['reference']['seconds']/pair['records']['native']['seconds']
        pair['same_full_state']=True
        result['pairs'].append(pair)
        target.write_text(json.dumps(result,indent=2)+'\n')
    result['summary']={}
    for backend in ('native','reference'):
        values=[p['records'][backend]['seconds'] for p in result['pairs']]
        result['summary'][backend]={'seconds':values,'median':statistics.median(values),'minimum':min(values),'maximum':max(values)}
    result['speedup']=result['summary']['reference']['median']/result['summary']['native']['median']
    result['paired_speedups']=[p['speedup'] for p in result['pairs']]
    result['load_after']=os.getloadavg()
    result['status']='COMPLETE'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'speedup':result['speedup'],'summary':result['summary']}),flush=True)


if __name__=='__main__':
    main()
