"""Chain bounded, input-verified recovery segments until a model terminal state."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,ROOT
enable()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--impl',choices=('fast','reference'),required=True)
    p.add_argument('--name',required=True);p.add_argument('--budget',type=int,default=4000000000)
    p.add_argument('--from-receipt',type=Path)
    a=p.parse_args();target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    result=dict(name=a.name,impl=a.impl,segments=[],load_before=os.getloadavg(),complete=False)
    resume=None;steps=0
    if a.from_receipt:
        prior=json.loads(a.from_receipt.read_text());resume=prior['snapshot']['path'];steps=prior['steps']
        result['development_continuation']=str(a.from_receipt)
    began=time.perf_counter()
    while steps<a.budget:
        name=a.name+'-s'+str(len(result['segments'])+1)
        argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),'1700',str(HERE/'scripts/recovery_long.py'),
              '--impl',a.impl,'--name',name,'--span',str(min(250000000,a.budget-steps))]
        if resume:argv+=['--resume',resume]
        child_start=time.perf_counter()
        with (HERE/'runs'/(name+'.log')).open('w') as log:
            child=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1750)
        if child.returncode:raise RuntimeError('recovery segment failed: '+name)
        record_path=HERE/'runs'/(name+'.json');record=json.loads(record_path.read_text())
        result['segments'].append(dict(receipt=str(record_path),seconds=time.perf_counter()-child_start,steps=record['steps']))
        steps=record['steps'];resume=record['snapshot']['path']
        result.update(steps=steps,seconds=time.perf_counter()-began,final=record,
                      status=record['status'],load_after=os.getloadavg())
        target.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(name=a.name,steps=steps,status=record['status'],seconds=result['seconds'])),flush=True)
        if record['terminal']:break
    if not result.get('final',{}).get('terminal'):
        result['status']='budget-without-completion';target.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
