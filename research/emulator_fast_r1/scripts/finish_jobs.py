"""Final short checks, serial first, then the same suite in two processes."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,ROOT
enable()


def main():
    tasks=[
        ('snapshots',[str(HERE/'scripts/snapshot_check.py'),'--name','snapshots-final3'],600),
        ('serial-suite',[str(HERE/'scripts/suite.py'),'--name','serial-final3','--jobs','1'],1700),
        ('parallel-suite',[str(HERE/'scripts/suite.py'),'--name','parallel-final3','--jobs','2'],1700),
        ('g145',[str(HERE/'g145_replay.py'),'--impl','batch','native-final3'],1200),
        ('compatibility',[str(HERE/'scripts/compatibility.py')],1200),
        ('recovery-native',[str(HERE/'scripts/full_recovery.py'),'--impl','fast','--name','recovery-native-final3','--budget','2000000000'],1700),
    ]
    records=[]
    for name,args,timeout in tasks:
        begin=time.perf_counter();load=os.getloadavg()
        argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),str(timeout),*args]
        with (HERE/'runs'/('final-'+name+'.log')).open('w') as log:
            result=subprocess.run(argv,cwd=ROOT,env={**os.environ,'GXR_EMULATOR_BATCH':'1'},stdout=log,stderr=subprocess.STDOUT,timeout=timeout+30)
        row=dict(task=name,exit_code=result.returncode,seconds=time.perf_counter()-begin,load_before=load,load_after=os.getloadavg())
        records.append(row);print(json.dumps(row),flush=True)
        (HERE/'runs/finish-jobs-final3.json').write_text(json.dumps(records,indent=2)+'\n')
        if result.returncode:break


if __name__=='__main__':main()
