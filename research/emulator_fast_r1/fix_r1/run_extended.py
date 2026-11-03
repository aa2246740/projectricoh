"""Run graph, borrowed state, numeric and actual function binding comparisons."""
import argparse,json,os,signal,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    signal.alarm(1200);assert os.getpriority(os.PRIO_PROCESS,0)>=15
    target=HERE/'runs'/(a.name+'.json');assert not target.exists()
    results=[]
    for case in (None,'before','after','code-before','code-after','default-before','genuine'):
        pair={}
        for backend in ('native','reference'):
            name=a.name+'-'+(case or 'states')+'-'+backend
            argv=[sys.executable,'-I','-B',str(HERE/'extended_cases.py'),'--backend',backend,'--name',name]
            if case:argv += ['--wrapper',case]
            with (HERE/'runs'/(name+'.log')).open('x') as log:
                child=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            assert child.returncode==0,(name,child.returncode)
            pair[backend]=json.loads((HERE/'runs'/(name+'.json')).read_text())
        if case:
            assert pair['native']['r0']==pair['reference']['r0']
            assert pair['native']['state']==pair['reference']['state']
        else:
            for name,row in pair['native']['cases'].items():
                other=pair['reference']['cases'][name]
                assert row['detail']==other['detail'] and row['state']==other['state'],name
        results.append(dict(case=case or 'states',passed=True,count=1 if case else len(pair['native']['cases'])))
        print(json.dumps(results[-1]),flush=True)
    target.write_text(json.dumps(dict(status='PASS',comparisons=results),indent=2)+'\n')


if __name__=='__main__':main()
