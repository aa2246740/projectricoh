"""Compare recognized wrapper closure bindings in independent processes."""
import argparse,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=15;signal.alarm(300)
    checks=[]
    for case in ('inner','peer','alias','genuine'):
        pair={}
        for backend in ('native','reference'):
            name=a.name+'-'+case+'-'+backend
            with (HERE/'runs'/(name+'.log')).open('x') as log:
                child=subprocess.run([sys.executable,'-I','-B',str(HERE/'hold_bindings.py'),'--backend',backend,
                       '--case',case,'--name',name],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=90)
            assert child.returncode==0,(name,child.returncode)
            pair[backend]=json.loads((HERE/'runs'/(name+'.json')).read_text())
        assert pair['native']['detail']==pair['reference']['detail'] and pair['native']['state']==pair['reference']['state'],case
        checks.append(dict(case=case,passed=True,native=pair['native']['native']['instructions']))
        print(json.dumps(checks[-1]),flush=True)
    target=HERE/'runs'/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(dict(status='PASS',checks=checks),indent=2)+'\n')


if __name__=='__main__':main()
