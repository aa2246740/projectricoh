"""Run three additional full retained groups with isolated products and temporary paths."""
from pathlib import Path
import difflib,hashlib,json,os,resource,subprocess,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')

def main():
    base=OUT/'real';base.mkdir(exist_ok=False)
    names=['group126-mount-half','group126-28mm-nested','group124+126-50mm-labels-g139']
    jobs=json.loads((ROOT/'research/g150/queue-reg.json').read_text())['jobs']
    chosen=[next(j for j in jobs if j['name']==name) for name in names]
    copies=[];records=[]
    for side in ('python','c'):
        entry=base/side;entry.mkdir();(entry/'local').mkdir()
        private=TMP/('real-'+side);private.mkdir(exist_ok=False)
        for source in sorted((OUT/'entry').glob('*.py'))+sorted((OUT/'entry/run').glob('*.py')):
            relative=source.relative_to(OUT/'entry');target=entry/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            a=source.read_text();b=a.replace(str(TMP),str(private))
            compile(b,str(target),'exec');target.write_text(b)
            copies.append({'source':str(source.relative_to(ROOT)),'copy':str(target.relative_to(ROOT)),
                           'source_sha256':hashlib.sha256(a.encode()).hexdigest(),'copy_sha256':hashlib.sha256(b.encode()).hexdigest(),
                           'diff':''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True)))})
        (entry/'offline.sb').write_bytes((OUT/'fence.sb').read_bytes())
        queue=entry/'queue.json';queue.write_text(json.dumps({'jobs':chosen},indent=2)+'\n')
    # Keep each side's first-run ordering explicit; no saved receipt is accepted here.
    for index,job in enumerate(chosen):
        for side in (('python','c') if index%2==0 else ('c','python')):
            entry=base/side;queue=entry/('queue-'+job['name']+'.json')
            queue.write_text(json.dumps({'jobs':[job]},indent=2)+'\n')
            name='real-'+str(index)+'-'+side
            env=dict(os.environ,GXR_HARNESS_BACKEND=side,TMPDIR=str(TMP/('real-'+side)))
            env.pop('GXR_CCORE_BUILD_MANIFEST',None)
            command=['/usr/bin/sandbox-exec','-f',str(OUT/'fence.sb'),'/usr/bin/python3','-I','-B',str(entry/'run.py'),'--name',name,'--queue',str(queue),'--slots','1']
            started=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
            print(json.dumps({'event':'start','job':job['name'],'backend':side}),flush=True)
            with (base/(name+'.log')).open('wb') as stream:
                result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
            after=resource.getrusage(resource.RUSAGE_CHILDREN)
            folder=entry/'local/runs'/name
            receipt=folder/'evidence/receipts'/(job['name']+'.json')
            processes=[json.loads(p.read_text()) for p in sorted((folder/'run/local/processes'/job['name']).glob('process-*.json'))]
            native={}
            for p in processes:
                for key,value in p['native_stats'].items():native[key]=native.get(key,0)+value
            row={'job':job['name'],'side':side,'name':name,'run':str(folder),'returncode':result.returncode,
                 'wall_seconds':time.monotonic()-started,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                 'timeout_seconds':10800,'historical_seconds':max([job.get('historical_seconds') or 0,*job.get('g139_seconds',{}).values()]),
                 'packets':sum(p['packets'] for p in processes),'native_stats':native,'processes':processes,
                 'command':command,'receipt':json.loads(receipt.read_text()) if receipt.exists() else None,
                 'load_end':os.getloadavg()}
            records.append(row);(base/'progress.json').write_text(json.dumps(records,indent=2)+'\n')
            print(json.dumps({k:v for k,v in row.items() if k not in ('processes','receipt','command')}),flush=True)
            if result.returncode:raise RuntimeError('real group did not finish successfully; inspect retained log')
    (base/'complete.json').write_text(json.dumps(records,indent=2)+'\n')
    (base/'copies.json').write_text(json.dumps(copies,indent=2)+'\n')

if __name__=='__main__':main()
