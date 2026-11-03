"""Paired whole retained jobs through the copied g150 scheduler, one slot."""
import argparse,asyncio,datetime,json,os,resource,shutil,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,TEMP,enable,emit,sha
from resume_identity import collect_inputs

def usage():
    r=resource.getrusage(resource.RUSAGE_CHILDREN)
    return r.ru_utime+r.ru_stime

def remove_tree(path):
    for item in path.iterdir():
        if item.is_dir() and not item.is_symlink():remove_tree(item)
        else:item.unlink()
    path.rmdir()

async def main():
    p=argparse.ArgumentParser();p.add_argument('--only',nargs='*');args=p.parse_args()
    enable()
    import run_regressions as runner
    jobs=json.loads((HERE/'queue.json').read_text())['jobs']
    if args.only:jobs=[j for j in jobs if j['name'] in args.only or j.get('group') in args.only or j['name']=='user-tool']
    out=HERE/'local/measurements';out.mkdir(exist_ok=True)
    records=[]
    for index,job in enumerate(jobs):
        name=job['name']
        sides=('python','c') if index%2==0 else ('c','python')
        if name in ('group124+126-50mm-safety','group126-28mm-exits','group126-mount-cutpoints','group126-50mm-view-reentry','group126-28mm-users'):sides+=('c-before',)
        for side in sides:
            evidence=out/side/name; receipt=evidence/'measurement.json'
            if evidence.exists():raise FileExistsError('fresh measurement directory required: '+str(evidence))
            work=HERE/'run/local/jobs'/name
            if work.exists():remove_tree(work)
            prior=HERE/'evidence/receipts'/(name+'.json')
            if prior.exists():prior.unlink()
            metrics=HERE/'run/local/processes'/side/name
            inputs=HERE/'run/local/inputs'/side/name
            os.environ.update(GXR_HARNESS_BACKEND='c' if side=='c-before' else side,GXR_HOST_METRICS_DIR=str(metrics),GXR_INPUT_RECEIPT_DIR=str(inputs),GXR_HARNESS_UI_AUDIT='1')
            if side=='c-before':os.environ['GXR_SPEEDLAB_COMPARE_API5']='1'
            else:os.environ.pop('GXR_SPEEDLAB_COMPARE_API5',None)
            os.environ.pop('GXR_CCORE_BUILD_MANIFEST',None)
            os.environ.pop('REVIEW_ONLY_CASE',None);os.environ.pop('REVIEW_MENU_PROBE',None)
            started=time.monotonic();cpu=usage();load=os.getloadavg()
            result=await runner.run(job,asyncio.Semaphore(1))
            metric={'job':name,'backend':side,'cpu_seconds':usage()-cpu,'wall_seconds':time.monotonic()-started,
                'load_start':load,'load_end':os.getloadavg(),'nice':os.getpriority(os.PRIO_PROCESS,0),'slots':1,
                'result':result,'dat_sha256':runner.PIN}
            evidence.mkdir(parents=True)
            shutil.copytree(work,evidence/'products')
            shutil.copyfile(HERE/'local/logs'/(name+'.log'),evidence/'raw.log')
            process_records=[json.loads(p.read_text()) for p in sorted(metrics.glob('process-*.json'))]
            metric['runtime_inputs']=collect_inputs(inputs)
            metric['processes']=process_records
            metric['packets']=sum(v['packets'] for v in process_records)
            metric['native_stats']={}
            for r in process_records:
                for k,v in r['native_stats'].items():metric['native_stats'][k]=metric['native_stats'].get(k,0)+v
            metric['all_artifacts']={str(p.relative_to(evidence/'products')):sha(p) for p in sorted((evidence/'products').rglob('*')) if p.is_file()}
            emit(receipt,metric);records.append(metric);emit(out/'progress.json',records)
            print(json.dumps({k:metric[k] for k in ('job','backend','cpu_seconds','wall_seconds','packets','native_stats')}),flush=True)
            if result['returncode'] or result['execution']!='FINISHED':
                print((evidence/'raw.log').read_text()[-2400:],flush=True)
                raise RuntimeError('real group failed: '+name+' '+side)
    emit(out/'complete.json',{'passed':True,'jobs':len(jobs),'sides':['python','c'],'before_controls':5,'records':records})
if __name__=='__main__':asyncio.run(main())
