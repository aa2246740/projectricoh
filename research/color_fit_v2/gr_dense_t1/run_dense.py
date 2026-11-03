"""Finite local calculation batches. No agents, services, sleeps or polling."""
import sys
from pathlib import Path
import argparse
import concurrent.futures
import json
import os
import subprocess

HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'


def jobs():
    full, loo, hue, image = [], [], [], []
    for group in ('gr3','gr4_hdf'):
        for slot in ('01','02'):
            for level in ('a','b','c'):
                base=['--group',group,'--slot',slot,'--level',level,'--nfev','160']
                full.append((f'{group}_{slot}_{level}_full',base))
                for i in range(18):
                    loo.append((f'{group}_{slot}_{level}_loo_{i:02d}',base+['--kind','loo','--start',str(i)]))
                for i in range(6):
                    hue.append((f'{group}_{slot}_{level}_hue_{i:02d}',base+['--kind','hue','--start',str(i)]))
                if group=='gr4_hdf':
                    for i in range(2):
                        image.append((f'{group}_{slot}_{level}_image_{i:02d}',base+['--kind','image','--start',str(i)]))
    return dict(full=full,loo=loo,hue=hue,image=image)


def execute(job, force=False):
    name,args=job
    dst=LOCAL/'fits'/f'{name}.json'
    if '--resume' in args and dst.exists():
        prior=json.loads(dst.read_text())
        if prior['solver']['success'] or prior.get('solver_history'):
            return name+' retained; continuation already attempted or solver converged'
    if dst.exists() and not force:
        return name+' preserved'
    out=subprocess.run(['python3','-I','-B',str(HERE/'fit.py'),*args],cwd=HERE.parents[2],
        env={**os.environ,'TMPDIR':str(LOCAL/'tmp'),'OPENBLAS_NUM_THREADS':'1',
             'OMP_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1'},
        capture_output=True,text=True,timeout=55)
    log=LOCAL/'logs'/f'{name}.txt';log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(out.stdout+out.stderr)
    if out.returncode:
        raise RuntimeError(name+' failed: '+out.stderr[-2500:])
    return out.stdout.strip().split(' score ')[0]


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('full','loo','hue','image','resume'))
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--end',type=int,required=True)
    p.add_argument('--jobs',type=int,default=3)
    p.add_argument('--force',action='store_true')
    p.add_argument('--dry-run',action='store_true',help='List missing fits without computing or writing')
    p.add_argument('--levels',nargs='+',choices=('a','b','c'),default=['a','b','c'])
    a=p.parse_args()
    if a.dry_run:
        assert a.phase!='resume','Dry-run covers missing initial fits only'
        selected=[j for j in jobs()[a.phase] if j[0].split('_')[-2 if a.phase=='full' else -3] in a.levels]
        batch=selected[a.start:a.end]
        missing=[name for name,_ in batch if not (LOCAL/'fits'/f'{name}.json').exists()]
        print(json.dumps(dict(phase=a.phase,start=a.start,end=a.end,selected=len(batch),
                              preserved=len(batch)-len(missing),missing=missing),indent=2))
        sys.exit(0)
    if a.phase=='resume':
        queue=LOCAL/'resume_queue.json'
        if not queue.exists():
            files=sorted((LOCAL/'fits').glob('*.json'))
            assert len(files)==312,'Complete all initial comparisons before continuing failed solvers'
            selected=[]
            for path in files:
                d=json.loads(path.read_text())
                if d['level']=='a' or d['solver']['success']:continue
                args=['--group',d['group'],'--slot',d['slot'],'--level',d['level'],
                      '--kind',d['kind'],'--nfev','160','--resume']
                if d['index'] is not None:args+=['--start',str(d['index'])]
                selected.append((path.stem,args))
            queue.write_text(json.dumps(selected,indent=2)+'\n')
        selected=json.loads(queue.read_text())
        print('fixed same-fold continuation queue:',len(selected),flush=True)
    else:
        selected=[j for j in jobs()[a.phase] if j[0].split('_')[-2 if a.phase=='full' else -3] in a.levels]
    batch=selected[a.start:a.end]
    assert len(batch)<=6
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        fs=[pool.submit(execute,j,a.force or a.phase=='resume') for j in batch]
        for future in concurrent.futures.as_completed(fs):
            print(future.result(),flush=True)
