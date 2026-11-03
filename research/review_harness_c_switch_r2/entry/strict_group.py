"""Compare a real retained group using complete input tracing with its saved oracle."""
import asyncio,json,os,resource,shutil,sys,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha
from resume_identity import collect_inputs
def remove_absolute(path):
    for item in path.iterdir():
        if item.is_dir() and not item.is_symlink():remove_absolute(item)
        else:item.unlink()
    path.rmdir()

async def main():
    enable();import run_regressions as runner
    name=os.environ.get('GXR_SPEEDLAB_STRICT_JOB','group126-50mm-cutpoints');label=os.environ.get('GXR_SPEEDLAB_STRICT_LABEL','c-strict-final')
    job=next(j for j in json.loads((HERE/'queue.json').read_text())['jobs'] if j['name']==name)
    out=HERE/'local/measurements'/label/name;out.mkdir(parents=True,exist_ok=False)
    receipt=HERE/'evidence/receipts'/(name+'.json');log=HERE/'local/logs'/(name+'.log');work=HERE/'run/local/jobs'/name
    backup=HERE/'local/strict-backups'/label/name;backup.mkdir(parents=True,exist_ok=False)
    for path in (receipt,log,work):
        if path.exists():path.rename(backup/path.name)
    metrics=HERE/'run/local/processes'/label/name;inputs=HERE/'run/local/inputs'/label/name
    os.environ.update(GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1',GXR_HOST_METRICS_DIR=str(metrics),GXR_INPUT_RECEIPT_DIR=str(inputs))
    os.environ.pop('GXR_CCORE_BUILD_MANIFEST',None)
    spawn=asyncio.create_subprocess_exec
    async def start(*args,**kwargs):
        args=tuple(str(HERE/'run/backend_launch_strict.py') if value==str(HERE/'run/backend_launch.py') else value for value in args)
        return await spawn(*args,**kwargs)
    values=dict(vars(asyncio));values['create_subprocess_exec']=start;runner.asyncio=types.SimpleNamespace(**values)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.monotonic();load=os.getloadavg()
    try:
        result=await runner.run(job,asyncio.Semaphore(1));elapsed=time.monotonic()-started
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        assert result['returncode']==0 and result['execution']=='FINISHED'
        processes=[json.loads(p.read_text()) for p in sorted(metrics.glob('process-*.json'))]
        native={}
        for process in processes:
            for key,value in process['native_stats'].items():native[key]=native.get(key,0)+value
        shutil.copytree(work,out/'products');shutil.copyfile(log,out/'raw.log')
        metric={'job':name,'backend':label,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'wall_seconds':elapsed,
                'load_start':load,'load_end':os.getloadavg(),'nice':os.getpriority(os.PRIO_PROCESS,0),'slots':1,'result':result,
                'processes':processes,'packets':sum(p['packets'] for p in processes),'native_stats':native,
                'runtime_inputs':collect_inputs(inputs),'dat_sha256':runner.PIN,
                'all_artifacts':{str(p.relative_to(out/'products')):sha(p) for p in (out/'products').rglob('*') if p.is_file()}}
        emit(out/'measurement.json',metric)
        from compare_products import compare_group
        comparison=compare_group(name,label)
        proof=HERE/'local/strict-comparison-final.json' if label=='c-strict-final' else HERE/'local/comparisons-strict'/(name+'.json')
        emit(proof,comparison)
        assert comparison['equal'],comparison['differences']
        print(json.dumps({'passed':True,'wall_seconds':elapsed,'cpu_seconds':metric['cpu_seconds'],'packets':metric['packets'],'compared_values':comparison['compared_values']}),flush=True)
    finally:
        if work.exists():remove_absolute(work)
        for path in (receipt,log):
            if path.exists():path.unlink()
        for path in (receipt,log,work):
            prior=backup/path.name
            if prior.exists():prior.rename(path)
if __name__=='__main__':asyncio.run(main())
