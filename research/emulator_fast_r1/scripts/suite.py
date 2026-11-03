"""Run the complete M2b/M2c DAG with isolated case media and fixed result order."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST,ROOT
enable()
sys.path.insert(0,str(FAST))
from parallel import run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True);p.add_argument('--jobs',type=int,required=True)
    a=p.parse_args();output=HERE/'local'/a.name;assert not output.exists();output.mkdir()
    ids=['regression','model','cold','card','files','full','read-error','write-error','no-card','restart','readback','m2b','guard','m2c']
    dependencies={'restart':['files'],'readback':['restart'],'m2b':['regression','cold','card'],
                  'guard':['m2b','model','files','full','read-error','write-error','no-card','readback'],
                  'm2c':['guard']}
    cases=[]
    for case in ids:
        cases.append(dict(id=case,argv=[sys.executable,'-I','-B',str(HERE/'scripts/limit.py'),'1200',
                        str(HERE/'scripts/suite_case.py'),'--case',case,'--output',str(output)],
                          after=dependencies.get(case,[]),timeout=1250,
                          artifacts=[dict(id='semantic',path=str(output/(case+'-semantic.json')))]))
    manifest=dict(cwd=str(ROOT),cases=cases)
    (HERE/'runs'/(a.name+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    result=run(cases,a.jobs,HERE/'runs'/(a.name+'.json'),ROOT)
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
