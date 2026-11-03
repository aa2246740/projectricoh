"""Compare the additional P1 regressions in fresh processes."""
import argparse,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    signal.alarm(600);assert os.getpriority(os.PRIO_PROCESS,0)>=15
    checks=[]
    for case in ('nested-key','descriptor','integer-subclass','shared-tuple','wrong-base-binding','irq-pending','timer-register','class-getattribute','missing-owner','float-clock','custom-list','mx-request','observer-counter','callback-wide-counter'):
        pair={}
        for backend in ('native','reference'):
            name=a.name+'-'+case+'-'+backend
            with (HERE/'runs'/(name+'.log')).open('x') as log:
                child=subprocess.run([sys.executable,'-I','-B',str(HERE/'additional_cases.py'),
                       '--backend',backend,'--case',case,'--name',name],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=120)
            assert child.returncode==0,(name,child.returncode)
            pair[backend]=json.loads((HERE/'runs'/(name+'.json')).read_text())
        native=pair['native']['native']
        passed=pair['native']['detail']==pair['reference']['detail'] and pair['native']['state']==pair['reference']['state']
        passed=passed and (not native or native['instructions']==0)
        if case=='missing-owner':passed=passed and not pair['native']['detail']['supported']
        checks.append(dict(case=case,passed=passed,native_instructions=native['instructions'] if native else 0))
        print(json.dumps(checks[-1]),flush=True)
    result=dict(status='PASS' if all(x['passed'] for x in checks) else 'FAIL',checks=checks)
    target=HERE/'runs'/(a.name+'.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
    assert result['status']=='PASS'


if __name__=='__main__':main()
