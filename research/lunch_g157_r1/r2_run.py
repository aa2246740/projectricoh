"""Admission queue for evaluation-only R2 stages."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r2_common import C
import argparse
import fcntl
import subprocess
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=('prepare','evaluate','blue','verify','report'))
    p.add_argument('--ids',nargs='*')
    p.add_argument('--max-workers',type=int,default=2)
    args=p.parse_args()
    lock=(C.LOCAL/'queue.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.stage=='evaluate':
        rows=C.read(C.LOCAL/'styles.json')
        jobs=[(r['id'],[str(C.HERE/'r2_evaluate.py'),r['id']],C.LOCAL/'results'/r['id']/'result.json')
              for r in rows if not args.ids or r['id'] in args.ids]
    else:
        target=dict(prepare='inputs.json',blue='blue.json',verify='verification.json',report='report.json')[args.stage]
        jobs=[(args.stage,[str(C.HERE/('r2_'+args.stage+'.py'))],C.LOCAL/target)]
    jobs=[j for j in jobs if not j[2].exists()]
    sys.path.insert(0,str(C.ROOT/'tools'));import loadgate
    tag=C.datetime.datetime.now(C.datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=C.LOCAL/'queues'/(args.stage+'-'+tag);root.mkdir(parents=True,exist_ok=False)
    running={};receipts=[];failed=[];last=0
    while jobs or running:
        for key,(proc,log,job,began) in list(running.items()):
            code=proc.poll()
            if code is None:continue
            log.close();del running[key]
            receipts.append(dict(id=key,exit_code=code,seconds=time.time()-began,pid=proc.pid))
            print('FINISH',key,code,flush=True)
            if code==75:jobs.append(job)
            elif code!=0 or not job[2].exists():failed.append(key)
        if failed and not running:break
        if jobs and not failed:
            cap,info=loadgate.cap(len(running),per_queue_max=args.max_workers)
            with (root/'admission.jsonl').open('a') as f:f.write(C.json.dumps(dict(utc=C.utc(),**info))+'\n')
            if cap>len(running):
                job=jobs.pop(0);key,argv,done=job
                proof=root/(key+'-'+str(len(receipts))+'-admission.json')
                proof.write_text(C.json.dumps(dict(parent_pid=C.os.getpid(),label='r2-'+key,running_before=len(running),**info)))
                log=(root/(key+'-'+str(len(receipts))+'.log')).open('w')
                env=dict(C.os.environ,LUNCH_QUEUE_ADMISSION=str(proof))
                proc=subprocess.Popen([sys.executable,'-I','-B',*argv],cwd=C.ROOT,stdout=log,stderr=subprocess.STDOUT,env=env)
                running[key]=proc,log,job,time.time()
                print('START',key,'idle cores',info['idle_cores'],flush=True)
        if time.time()-last>40:
            print('QUEUE',args.stage,'pending',len(jobs),'running',list(running),'failed',failed,flush=True);last=time.time()
        C.dump(root/'receipt.json',dict(rows=receipts,pending=[j[0] for j in jobs],running=list(running),failed=failed))
        if jobs or running:time.sleep(2 if running else 10)
    if failed:raise SystemExit('Failure preserved, no automatic numerical retry: '+','.join(failed))
    print('COMPLETE',args.stage,len(receipts),flush=True)


if __name__=='__main__':main()
