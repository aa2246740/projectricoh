"""Prove second-controller refusal and child-held lease lifetime locally."""
from pathlib import Path
import fcntl,json,os,select,subprocess,sys,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152/guard')
sys.path.insert(0,str(HERE))
from controller_guard import LEASE
def main():
    TMP.mkdir(parents=True,exist_ok=False);fifo=TMP/'ready';os.mkfifo(fifo);read_fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK)
    made=[];rows=[]
    def ready():
        assert select.select([read_fd],[],[],30)[0],'No fixture ready event.'
        return json.loads(os.read(read_fd,4096).decode())
    def controller(label,hold=False):
        output=HERE/'local'/('guard-'+label+'.json');queue=TMP/(label+'.json')
        args=['--output',str(output)]+(['--hold','--ready',str(fifo)] if hold else [])
        queue.write_text(json.dumps([dict(name='guard-'+label,script='guard_fixture.py',args=args,timeout=120,outputs=[str(output.relative_to(HERE))])]))
        p=subprocess.Popen(['/usr/bin/python3','-I','-B',str(HERE/'run_jobs.py'),str(queue)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        made.append(p);return p
    try:
        owner=controller('owner',True);first=ready()
        blocked=controller('blocked');out=blocked.communicate(timeout=30)[0]
        assert blocked.returncode!=0 and 'CONTROLLER_BUSY' in out
        owner.stdin.write('done\n');owner.stdin.flush();owner.wait(timeout=30);assert owner.returncode==0
        rows.append(dict(case='second_controller_refused',status='PASS',worker=first))
        handle=LEASE.open('a+');fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        output=HERE/'local/guard-inherited.json';env=dict(os.environ,G152_CONTROLLER_LEASE_FD=str(handle.fileno()))
        command=['/usr/bin/nice','-n','10','/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),'/usr/bin/python3','-I','-B',str(HERE/'guard_fixture.py'),'--hold','--ready',str(fifo),'--output',str(output)]
        child=subprocess.Popen(command,cwd=ROOT,env=env,pass_fds=(handle.fileno(),),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);made.append(child)
        second=ready();handle.close()
        blocked=controller('inherited-blocked');out=blocked.communicate(timeout=30)[0]
        assert blocked.returncode!=0 and 'CONTROLLER_BUSY' in out
        child.stdin.write('done\n');child.stdin.flush();child.wait(timeout=30);assert child.returncode==0
        rows.append(dict(case='child_retains_lease_after_parent_close',status='PASS',worker=second))
        released=controller('released');out=released.communicate(timeout=30)[0];assert released.returncode==0,out
        rows.append(dict(case='next_controller_after_exit',status='PASS'))
        owner=controller('signal',True);third=ready();owner.terminate();owner.wait(timeout=30)
        assert owner.returncode!=0
        after=subprocess.check_output(['/bin/ps','-axo','pid=,command='],text=True)
        assert not any(line.strip().split(None,1)[0]==str(third['pid']) for line in after.splitlines() if line.strip())
        rows.append(dict(case='signal_waits_for_test_exit',status='PASS',worker=third))
        result=dict(status='PASS',cases=rows,scope='Local controller fixtures only; no camera model, network or device action.',ended_ns=time.time_ns())
        (HERE/'evidence/controller_guard.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:
        for p in made:
            if p.poll() is None:p.terminate();p.wait(timeout=30)
        os.close(read_fd)
if __name__=='__main__':main()
