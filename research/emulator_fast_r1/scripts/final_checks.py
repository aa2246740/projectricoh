"""Bounded final checks against one frozen implementation."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,ROOT
enable()


def main():
    fixes='sd-long-response,nand-read-tail,nand-word,preview-link'
    tasks=[]
    for backend in ('native','reference'):
        for selected in ('',fixes):
            name='corrections-'+backend+('-all' if selected else '-default')+'-final10'
            tasks.append((name,[str(HERE/'scripts/native_corrections.py'),'--name',name,'--backend',backend,'--fixes',selected],180,{}))
    tasks +=[
        ('snapshots-final9',[str(HERE/'scripts/snapshot_check.py'),'--name','snapshots-final9'],600,{}),
        ('suite-prime-final9',[str(HERE/'scripts/suite.py'),'--name','suite-prime-final9','--jobs','1'],1700,{'GXR_FAST_CASE_CACHE':str(HERE/'local/prepared-cache-final9')}),
        ('serial-final9',[str(HERE/'scripts/suite.py'),'--name','serial-final9','--jobs','1'],1700,{'GXR_FAST_CASE_CACHE':str(HERE/'local/prepared-cache-final9')}),
        ('parallel-final9',[str(HERE/'scripts/suite.py'),'--name','parallel-final9','--jobs','2'],1700,{'GXR_FAST_CASE_CACHE':str(HERE/'local/prepared-cache-final9')}),
        ('g145-final9',[str(HERE/'g145_replay.py'),'--impl','batch','native-final9'],1200,{}),
        ('mutation-final9',[str(HERE/'scripts/mutation_check.py'),'--name','mutation-final9'],180,{}),
        ('recovery-default-final9',[str(HERE/'scripts/full_recovery.py'),'--impl','fast','--name','recovery-default-final9','--budget','2000000000'],1700,{}),
    ]
    records=[]
    for name,args,timeout,extra in tasks:
        began=time.perf_counter();load=os.getloadavg()
        argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),str(timeout),*args]
        with (HERE/'runs'/(name+'.log')).open('w') as log:
            child=subprocess.run(argv,cwd=ROOT,env={**os.environ,**extra,'GXR_EMULATOR_BATCH':'1'},stdout=log,stderr=subprocess.STDOUT,timeout=timeout+30)
        records.append(dict(name=name,exit_code=child.returncode,seconds=time.perf_counter()-began,load_before=load,load_after=os.getloadavg()))
        (HERE/'runs/final-checks-final10.json').write_text(json.dumps(records,indent=2)+'\n')
        print(json.dumps(records[-1]),flush=True)
        if child.returncode:raise SystemExit(child.returncode)


if __name__=='__main__':main()
