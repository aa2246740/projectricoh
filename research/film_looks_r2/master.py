"""One restartable queue for fits, exact confirmation, position checks and publication inputs."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

assert sys.flags.isolated
HERE=Path(__file__).resolve().parent;LOCAL=HERE/'local'
UNITS=('mount-a12','a12-28','a12-50')
ROUTES=('scene_shared_matrix','scene_shared_structure','scene_rgb_matrix','scene_structure','scene_weighted')
STYLE_ORDER=(6,17,18,23,16,10,50,51,52,9,15,0,1,2,3)
REVISION='r3_unweighted_primary_weighted_control'


def read(p):return json.loads(Path(p).read_text())
def fitpath(unit,index,phase='iterate'):return LOCAL/'fits'/unit/str(index)/(phase+'.json')
def sourcepath(unit,index):
    p=fitpath(unit,index,'exact')
    return p if p.exists() else fitpath(unit,index)
def film_signature(film,unit):
    values={}
    for r in ROUTES:
        p=sourcepath(unit,film['indices'][r])
        if not p.exists():return None
        d=read(p);values[r]=dict(phase=d['phase'],record=d['record_sha256'])
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
def active_workers():
    names={'library.py','styles.py','analyze.py','analyze_style.py','look_structure.py','acros_full.py'}
    out=[]
    for line in subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines():
        parts=line.strip().split(None,1)
        if len(parts)<2:continue
        # ps supplies process data, not a shell command to unquote.
        args=parts[1].split()
        if not args or not Path(args[0]).name.lower().startswith('python'):continue
        if any('film_looks_r2/' in x and Path(x).name in names for x in args):out.append(int(parts[0]))
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--max-workers',type=int,default=6)
    p.add_argument('--confirm-admitted-weighting',action='store_true');a=p.parse_args()
    assert 1<=a.max_workers<=6
    if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
    assert os.getpriority(os.PRIO_PROCESS,0)==15
    root=LOCAL/'batches'/a.tag;root.mkdir(parents=True,exist_ok=False)
    while active_workers():
        print('DRAIN previous workers',active_workers(),flush=True);time.sleep(5)
    cat=read(LOCAL/'catalog.json');running={};rows=[];failed=set();cooldown={};last=0;turn=0
    order=[0,9,14,15,16,17,18,19]+[i for i in range(20) if i not in (0,9,14,15,16,17,18,19)]
    def make(key,script,args,out,category,refresh=False):
        return dict(key=key,command=[sys.executable,'-I','-B',str(HERE/script),*args],out=out,category=category,refresh=refresh)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.max_workers) as pool:
        while True:
            for key,f in list(running.items()):
                if not f.done():continue
                row=f.result();rows.append(row);del running[key]
                print('FINISH',key,row['exit_code'],round(row['seconds'],1),flush=True)
                if row['exit_code']==75:cooldown[key]=time.monotonic()+12
                elif row['exit_code']!=0:failed.add(key)
                (root/'receipt.json').write_text(json.dumps(dict(rows=rows,failed=sorted(failed)),indent=2)+'\n')
            jobs=[];film_done=0;style_done=0
            if not (LOCAL/'acros_full_profiles.json').exists():
                jobs.append(make('acros-prepare','acros_full.py',['prepare'],LOCAL/'acros_full_profiles.json','short'))
            else:
                for unit in UNITS:
                    for phase,nfev in (('iterate',160),('exact',400)):
                        out=fitpath(unit,4053,phase)
                        if not out.exists():
                            jobs.append(make('acros-'+unit+'-'+phase,'acros_full.py',[phase,'--unit',unit,'--nfev',str(nfev)],out,'short'));break
            for ordinal in order:
                film=cat['films'][ordinal];prepared=LOCAL/'films'/f'{ordinal:02d}/prepared.json'
                if not prepared.exists():
                    jobs.append(make(f'{ordinal:02d}-prepare','library.py',['prepare','--film',str(ordinal)],prepared,'film'));continue
                if not (LOCAL/'films'/f'{ordinal:02d}/look-structure-prepared.json').exists():
                    out=LOCAL/'films'/f'{ordinal:02d}/look-structure-prepared.json'
                    jobs.append(make(f'{ordinal:02d}-shared-prepare','look_structure.py',['--film',str(ordinal)],out,'film'));continue
                for unit in UNITS:
                    base=LOCAL/'analysis'/f'{ordinal:02d}'/unit
                    signature=film_signature(film,unit)
                    final=base/'final.json'
                    if final.exists():
                        doc=read(final)
                        if (doc.get('analysis_revision')==REVISION and doc.get('input_fit_signature')==signature
                            and doc.get('placement_classification_complete')):
                            film_done+=1;continue
                    needed=list(ROUTES)
                    if ordinal==9:needed=['scene_shared','scene_rgb',*needed]
                    for route in needed:
                        idx=film['indices'][route];out=fitpath(unit,idx)
                        if out.exists():continue
                        parents={'scene_rgb':('scene_shared',),'scene_rgb_matrix':('scene_shared_matrix',),
                            'scene_weighted':('scene_structure',)}.get(route,())
                        if ordinal==9 and route=='scene_shared_matrix':parents=('scene_shared',)
                        if ordinal==9 and route=='scene_rgb_matrix':parents=('scene_rgb','scene_shared_matrix')
                        if all(fitpath(unit,film['indices'][r]).exists() for r in parents):
                            jobs.append(make(f'{ordinal:02d}-{unit}-{route}-iterate','library.py',
                                ['iterate','--film',str(ordinal),'--unit',unit,'--route',route,'--nfev','160'],out,'film'))
                    if signature is None:continue
                    screen=base/'screen.json'
                    if (not screen.exists() or read(screen).get('input_fit_signature')!=signature or
                        read(screen).get('analysis_revision')!=REVISION):
                        jobs.append(make(f'{ordinal:02d}-{unit}-screen','analyze.py',
                            ['--film',str(ordinal),'--unit',unit,'--phase','screen'],screen,'film',screen.exists()));continue
                    sc=read(screen);confirm={sc['selected_route'],sc['selected_Look_route']}
                    if a.confirm_admitted_weighting:
                        default=sc['routes'][sc['selected_route']]['scores']['photo_iso200']
                        weighted=sc['routes']['scene_weighted']['scores']['photo_iso200']
                        ds,ws=default['similarity_percent'],weighted['similarity_percent']
                        m0=default['color_regions'];m1=weighted['color_regions']
                        shared=[k for k in ('skin','sky','foliage') if m0[k]['n']>=20 and m1[k]['n']>=20]
                        if (shared and ds is not None and ws is not None and ws>=ds-1 and
                            weighted['de00']['p95']<=default['de00']['p95']+.25 and
                            sum(m1[k]['median'] for k in shared)<sum(m0[k]['median'] for k in shared)-.05 and
                            all(m1[k]['median']<=m0[k]['median']+.25 for k in shared)):
                            confirm.add('scene_weighted')
                    missing=[r for r in confirm if not fitpath(unit,film['indices'][r],'exact').exists()]
                    for route in sorted(missing):
                        out=fitpath(unit,film['indices'][route],'exact')
                        jobs.append(make(f'{ordinal:02d}-{unit}-{route}-exact','library.py',
                            ['exact','--film',str(ordinal),'--unit',unit,'--route',route,'--nfev','400'],out,'film'))
                    if not missing:
                        jobs.append(make(f'{ordinal:02d}-{unit}-final','analyze.py',
                            ['--film',str(ordinal),'--unit',unit,'--phase','final'],final,'film',final.exists()))
            if not (LOCAL/'styles.json').exists():
                jobs.append(make('styles-prepare','styles.py',['prepare'],LOCAL/'styles.json','style'))
            else:
                for oldindex in (*STYLE_ORDER,53):
                    for unit in UNITS:
                        out=LOCAL/'style_analysis'/f'{oldindex:02d}'/(unit+'.json')
                        if out.exists():style_done+=1;continue
                        indices=(14,4053) if oldindex==53 else (3000+10*oldindex,3001+10*oldindex)
                        if all(fitpath(unit,i,'exact').exists() for i in indices):
                            jobs.append(make(f'style-{oldindex:02d}-{unit}-analyze','analyze_style.py',
                                ['--index',str(oldindex),'--unit',unit],out,'style'));continue
                        if oldindex==53:continue
                        prior=True
                        for index in indices:
                            for phase,nfev in (('iterate',160),('exact',400)):
                                done=fitpath(unit,index,phase).exists()
                                if prior and not done:
                                    jobs.append(make(f'style-{oldindex:02d}-{unit}-{index}-{phase}','styles.py',
                                        [phase,'--index',str(index),'--unit',unit,'--nfev',str(nfev)],fitpath(unit,index,phase),'style'))
                                prior=prior and done
            if film_done==60 and style_done==48 and not running:break
            if failed:
                if not running:break
                time.sleep(2);continue
            line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip();match=re.search(r'load averages?:\s*([\d.]+)',line)
            if not match:raise RuntimeError('Cannot parse uptime')
            load=float(match[1]);limit=0 if load>10 else min(a.max_workers,6 if load<5 else 2)
            ready=[j for j in jobs if j['key'] not in running and time.monotonic()>=cooldown.get(j['key'],0)]
            capacity=max(0,limit-len(running))
            selected=[]
            for unused in range(capacity):
                short=next((j for j in ready if j['category']=='short'),None)
                category='film' if turn%2==0 else 'style'
                job=short or next((j for j in ready if j['category']==category),None) or (ready[0] if ready else None)
                if job is None:break
                ready.remove(job);selected.append(job);turn+=1
            for job in selected:
                key=job['key'];log=root/(key+'-'+datetime.datetime.now().strftime('%H%M%S')+'.log')
                if job['refresh'] and job['out'].exists():
                    archived=job['out'].parent/'history'/(job['out'].stem+'-'+datetime.datetime.now().strftime('%H%M%S')+'.json')
                    archived.parent.mkdir(exist_ok=True);archived.write_bytes(job['out'].read_bytes())
                def one(job=job,log=log,line=line):
                    began=time.monotonic()
                    with log.open('w') as f:r=subprocess.run(job['command'],stdout=f,stderr=subprocess.STDOUT)
                    return dict(key=job['key'],command=job['command'],log=str(log),uptime=line,
                        exit_code=r.returncode,seconds=time.monotonic()-began)
                running[key]=pool.submit(one);print('START',key,'load1',load,flush=True)
            if time.monotonic()-last>45:
                print('MASTER',film_done,'/60 films,',style_done,'/48 styles, running',len(running),'load1',load,flush=True)
                (LOCAL/'master_progress.json').write_text(json.dumps(dict(film_final=film_done,style_final=style_done,
                    running=list(running),load1=load,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
                last=time.monotonic()
            time.sleep(2)
    if failed:raise SystemExit('Master failures: '+','.join(sorted(failed)))
    (LOCAL/'master_complete.json').write_text(json.dumps(dict(films=60,styles=48,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
    print('MASTER COMPLETE:60 film profiles,48 style profiles',flush=True)


if __name__=='__main__':main()
