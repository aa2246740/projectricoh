"""Author the finite acceptance queue; no emulator or compiler runs here."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def main():
    C.setup();p=argparse.ArgumentParser();p.add_argument('--append-replays',action='store_true');a=p.parse_args()
    file=C.LOCAL/'r1-work.json'
    tasks=json.loads(file.read_text()) if a.append_replays else []
    def add(id,script,args=(),needs=(),**extra):
        tasks.append(dict(id=id,script=script,args=list(args),needs=list(needs),log=str(C.LOCAL/'logs'/(id+'.log')),**extra))
    def cold(dataset,profile,unit,action='menu',tail=(),suffix=None,needs=(),backend='native'):
        label='r1-'+dataset+'-'+profile+'-'+unit+'-'+(suffix or action)+'-'+backend
        deps=list(needs)+(['link-model-'+profile] if dataset=='model' else [])
        add(label,'run.py',['--dataset',dataset,'--version',profile,'--unit',unit,'--backend',backend,'--label',label,'--action',action,*tail],deps)
        return label
    if not a.append_replays:
        add('link-model-test','build.py',['--dataset','model','--profile','test'],link=True)
        add('link-model-release','build.py',['--dataset','model','--profile','release'],['link-model-test'],link=True)
        source_jobs={}
        for dataset in ('model','control'):
            source_jobs[dataset]=[]
            linked=['link-model-test','link-model-release'] if dataset=='model' else []
            for profile in ('test','release'):
                fixture=cold(dataset,profile,'mount')
                for backend in ('c','python'):
                    add(f'{dataset}-service-{profile}-{backend}','service_probe.py',['--dataset',dataset,'--profile',profile,'--backend',backend,'--fixture',str(C.LOCAL/'runs'/fixture/'service-fixture/manifest.json')],[fixture])
            add(dataset+'-static','static.py',['--dataset',dataset],linked)
            for backend in ('c','python'):
                add(dataset+'-host-'+backend,'host_probe.py',['--dataset',dataset,'--backend',backend],linked)
        # Source sessions precede long sweeps so their complete S blocks are ready.
        for dataset in ('model','control'):
            for profile in ('test','release'):
                for name,row in (('hcbw',2),('portra',11),('lowsat',14)):
                    for close in ('OK','ADJ'):
                        label='r1-'+('' if dataset=='control' else 'model-')+f'session-{profile}-{name}-{close}'
                        deps=['link-model-'+profile] if dataset=='model' else []
                        add(label,'run.py',['--dataset',dataset,'--version',profile,'--unit','mount','--backend','native','--label',label,'--action','session','--session-row',str(row),'--close-key',close],deps)
                        source_jobs.setdefault(dataset,[]).append(label)
            add(dataset+'-prepare-S48','replay.py',['--dataset',dataset,'--tag','r1','--prepare-replays'],source_jobs[dataset])
        for dataset in ('model','control'):
            for profile in ('test','release'):
                for unit in C.UNITS:cold(dataset,profile,unit,'sweep')
        # Reference devices and Python instruction execution recheck all units.
        for unit in C.UNITS:
            cold('model','test',unit,'sweep',['--only','0,17'],suffix='critical',backend='reference')
            cold('model','release',unit,'menu',backend='reference')
        for challenge in ('boot-activity6','boot-mode4','boot-both','no-dispatch','boot-vivid','boot-wb'):
            cold('model','test','mount','menu',['--challenge',challenge],suffix=challenge)
        add('byte-audit','audit.py',[],['link-model-test','link-model-release','control-static','model-static'])
    else:
        known={t['id'] for t in tasks}
        for dataset in ('model','control'):
            q=C.LOCAL/('persistence-r1-'+dataset)/'replays.queue.json'
            if not q.exists():continue
            for row in json.loads(q.read_text()):
                if row['label'] not in known:add(row['label'],'run.py',row['args'])
            verify=dataset+'-S48-verification'
            if verify not in known:add(verify,'replay.py',['--dataset',dataset,'--tag','r1','--verify'],[r['label'] for r in json.loads(q.read_text())])
    temp=file.with_suffix('.tmp');C.save(temp,tasks);temp.replace(file)
    print(json.dumps(dict(tasks=len(tasks))))

if __name__=='__main__':main()
