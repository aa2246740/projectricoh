"""Alternate the original batch tool and native tool on identical declared inputs."""
import argparse,json,os,statistics,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST,ROOT
enable()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True);p.add_argument('--repetitions',type=int,default=5)
    a=p.parse_args();target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    sources={str(p.relative_to(FAST)):__import__('hashlib').sha256(p.read_bytes()).hexdigest()
             for p in sorted(FAST.iterdir()) if p.suffix in ('.py','.c','.h','.inc','.json')}
    result=dict(name=a.name,repetitions=a.repetitions,raw=[],summary={},source_hashes=sources,
                load_before=os.getloadavg(),nice=os.getpriority(os.PRIO_PROCESS,0))
    began=time.perf_counter()
    for kind,points in [('main','1000000,50000000'),('boot','1000000,35537208,50000000,202997601'),('recovery','1000000,50000000,65975242')]:
        records={'batch':[],'fast':[]}
        for index in range(a.repetitions):
            order=('batch','fast') if index%2==0 else ('fast','batch')
            pair={}
            for impl in order:
                name=f'{a.name}-{kind}-{index+1}-{impl}'
                argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),'1700',str(HERE/'scripts/workload.py'),
                      '--impl',impl,'--kind',kind,'--name',name,'--points',points]
                t=time.perf_counter()
                with (HERE/'runs'/(name+'.log')).open('w') as log:
                    child=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1750)
                if child.returncode:raise RuntimeError('benchmark child failed: '+name)
                record=json.loads((HERE/'runs'/(name+'.json')).read_text());assert record['status']=='complete'
                record['process_wall_seconds']=time.perf_counter()-t
                records[impl].append(record);pair[impl]=record
                result['raw'].append(str(HERE/'runs'/(name+'.json')))
                print(json.dumps(dict(kind=kind,repetition=index+1,impl=impl,seconds=sum(x['seconds'] for x in record['segments']))),flush=True)
            if pair['batch']['points']!=pair['fast']['points']:
                raise AssertionError('whole-state mismatch in '+kind+' pair '+str(index+1))
            native=pair['fast']['native_machine']
            assert native['instructions']==int(points.split(',')[-1]) and native['python_bus_calls']==0 and not native['hle_callbacks']
            result['summary'][kind]=dict()
            for impl in ('batch','fast'):
                values=[sum(x['seconds'] for x in record['segments']) for record in records[impl]]
                result['summary'][kind][impl]=dict(seconds=values,median=statistics.median(values),minimum=min(values),maximum=max(values))
            result['summary'][kind]['speedup']=result['summary'][kind]['batch']['median']/result['summary'][kind]['fast']['median']
            result['summary'][kind]['all_states_equal']=True
            result['seconds']=time.perf_counter()-began;result['load_after']=os.getloadavg()
            target.write_text(json.dumps(result,indent=2)+'\n')
    actual={str(p.relative_to(FAST)):__import__('hashlib').sha256(p.read_bytes()).hexdigest()
            for p in sorted(FAST.iterdir()) if p.suffix in ('.py','.c','.h','.inc','.json')}
    assert actual==sources,'native source files changed during benchmark'
    result['status']='complete';target.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
