"""Optional g150 runner entry: one backend switch, independent runs, checked resume."""
import argparse,asyncio,fcntl,hashlib,json,os,platform,signal,sys,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha
from resume_identity import selection,collect_inputs,verify_inputs

class LoadSlots:
    def __init__(self,slots):
        self.slots=slots;self.active=0;self.condition=asyncio.Condition()
    async def __aenter__(self):
        async with self.condition:
            while self.active >= (1 if os.getloadavg()[0]>8 else self.slots):
                await self.condition.wait()
            self.active+=1
    async def __aexit__(self,*args):
        async with self.condition:
            self.active-=1;self.condition.notify_all()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name')
    parser.add_argument('--queue',type=Path,default=HERE/'queue.json')
    parser.add_argument('--slots',type=int,choices=(1,2),default=1)
    args=parser.parse_args();enable()
    if os.environ.get('GXR_SPEEDLAB_COMPARE_API5'):raise RuntimeError('API5 comparison is limited to measure.py')
    lock=(HERE/'local/scheduler.lock').open('a')
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    selected=os.environ.get('GXR_HARNESS_BACKEND','python')
    if selected not in ('python','c'):raise ValueError('GXR_HARNESS_BACKEND must be python or c')
    name=args.name or selected
    if not name.replace('-','').replace('_','').isalnum():raise ValueError('plain run name required')
    out=HERE/'local/runs'/name;out.mkdir(parents=True,exist_ok=True)
    code=out/'run';code.mkdir(exist_ok=True)
    profile=out/'offline.sb'
    if profile.exists() and profile.read_bytes()!=(HERE/'offline.sb').read_bytes():raise RuntimeError('sandbox profile drift; choose a new run name')
    if not profile.exists():profile.write_bytes((HERE/'offline.sb').read_bytes())
    # This copies only our relocated runner adapters. Test bodies remain read-only.
    for filename in ('legacy_call.py','fixture.py','users_gxui.py','backend_select.py','backend_launch.py','input_trace.py','input_trace_strict.py'):
        source=HERE/'run'/filename
        text=source.read_text()
        if filename=='backend_select.py':text=text.replace('from input_trace import InputTrace','from input_trace_strict import InputTrace')
        text=text.replace('ROOT = Path(__file__).resolve().parents[4]','ROOT = Path('+repr(str(ROOT))+')')
        text=text.replace("ROOT / 'tools/speedlab/host_regression_r4/run'",'Path('+repr(str(code))+')')
        text=text.replace("ROOT / 'tools/speedlab/host_regression_r4/run/local/decode'",'Path('+repr(str(code/'local/decode'))+')')
        target=code/source.name
        if target.exists() and target.read_text()!=text:raise RuntimeError('runner source drift; choose a new run name')
        if not target.exists():target.write_text(text)
    for subdir in ('evidence/receipts','local/logs'):(out/subdir).mkdir(parents=True,exist_ok=True)
    manifest=ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json'
    if selected=='c':
        build=json.loads(manifest.read_text())
        if build['python']!=sys.version or build['machine']!=platform.machine():raise RuntimeError('candidate ABI identity differs; rebuild required')
        if sha(Path(build['library']))!=build['sha256']:raise RuntimeError('candidate library identity differs; rebuild required')
        if any(not Path(path).is_file() or sha(Path(path))!=digest for path,digest in build['sources'].items()):raise RuntimeError('candidate source identity differs; rebuild required')
        os.environ['GXR_CCORE_BUILD_MANIFEST']=str(manifest)
    if selected=='c':os.environ.setdefault('GXR_HARNESS_UI_AUDIT','1')
    import run_regressions as runner
    runner.CHECKED_ENTRY=True
    runner.OUT=out
    queue=json.loads(args.queue.resolve().read_text())
    identity={'selection':selection(queue,args.slots),'identity_helper_sha256':sha(HERE/'resume_identity.py'),'entry_source_sha256':sha(Path(__file__)),'sandbox_sha256':sha(profile),'backend':selected,'dat_sha256':runner.PIN,'runner_source_sha256':sha(HERE/'run_regressions.py'),
              'adapters':{p.name:sha(p) for p in sorted(code.glob('*.py'))},
              'library_sha256':json.loads(manifest.read_text())['sha256'] if selected=='c' else None,
              'candidate_sources':json.loads(manifest.read_text())['sources'] if selected=='c' else None,
              'options':{k:v for k,v in os.environ.items() if k.startswith('GXR_HARNESS_')}}
    identity_path=out/'identity.json'
    if identity_path.exists() and json.loads(identity_path.read_text())!=identity:
        emit(out/'identity-rejected.json',{'expected':json.loads(identity_path.read_text()),'actual':identity})
        raise RuntimeError('resume identity differs; choose a new run name')
    emit(identity_path,identity)
    queue=json.loads(args.queue.resolve().read_text())
    jobs=queue['jobs']
    def history(job):return max([job.get('historical_seconds') or 0,*job.get('g139_seconds',{}).values()])
    prerequisites=[j for j in jobs if j['name']=='user-tool']
    jobs=prerequisites+sorted((j for j in jobs if j['name']!='user-tool'),key=history,reverse=True)
    for job in jobs:
        if not job['name'].replace('-','').replace('_','').replace('+','').replace('.','').isalnum():raise ValueError('invalid queue job name')
        job['timeout_seconds']=max(job.get('timeout_seconds',0),3*history(job),10800)
        job['env']=dict(job.get('env',{}),GXR_HARNESS_BACKEND=selected,GXR_HOST_METRICS_DIR=str(code/'local/processes'/job['name']))
    effective=out/'queue.json';emit(effective,{'jobs':jobs})
    original_run=runner.run
    def validate_prior(job):
        receipt=out/'evidence/receipts'/(job['name']+'.json')
        if receipt.exists():
            prior=json.loads(receipt.read_text())
            verify_inputs(prior.get('runtime_inputs'),code/'local/inputs'/job['name'])
            if prior.get('args')!=job['args'] or prior.get('env')!=job['env']:raise RuntimeError('resume job arguments differ')
            if prior.get('returncode')!=0 or prior.get('execution')!='FINISHED':raise RuntimeError('failed job needs a new run name')
            # Refuse reuse after loss or modification of the saved product tree.
            hashes=prior.get('product_hashes')
            work=code/'local/jobs'/job['name']
            current={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file()}
            if hashes!=current:raise RuntimeError('resume product identity differs')
            if sha(ROOT/prior['log'])!=prior['log_sha256']:raise RuntimeError('resume log identity differs')
            metrics=code/'local/processes'/job['name']
            current_metrics={p.name:sha(p) for p in sorted(metrics.glob('*.json'))}
            if current_metrics!=prior.get('metrics_hashes'):raise RuntimeError('resume process evidence differs')
    for job in jobs:validate_prior(job)
    class HeldSlot:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
    async def run(job,semaphore):
        async with semaphore:
            receipt=out/'evidence/receipts'/(job['name']+'.json')
            result=await original_run(job,HeldSlot())
            if 'product_hashes' not in result:
                work=code/'local/jobs'/job['name']
                result['product_hashes']={str(p.relative_to(work)):sha(p) for p in sorted(work.rglob('*')) if p.is_file()}
                metrics=code/'local/processes'/job['name']
                result['metrics_hashes']={p.name:sha(p) for p in sorted(metrics.glob('*.json'))}
                if result['returncode']==0 and result['execution']=='FINISHED':
                    result['runtime_inputs']=collect_inputs(code/'local/inputs'/job['name'])
                emit(receipt,result)
            return result
    runner.run=run
    owned=[]
    async def start_process(*argv,**kwargs):
        pending=asyncio.create_task(asyncio.create_subprocess_exec(*argv,**kwargs))
        try:process=await asyncio.shield(pending)
        except asyncio.CancelledError:
            process=await pending;owned.append(process);raise
        owned.append(process);return process
    values=dict(vars(asyncio));values['Semaphore']=LoadSlots;values['create_subprocess_exec']=start_process;runner.asyncio=types.SimpleNamespace(**values)
    async def supervised():
        try:await runner.main()
        finally:
            active=[p for p in owned if p.returncode is None]
            for process in active:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            if active:
                try:await asyncio.wait_for(asyncio.gather(*(p.wait() for p in active)),8)
                except asyncio.TimeoutError:
                    for process in active:
                        if process.returncode is None:
                            try:os.killpg(process.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                    await asyncio.gather(*(p.wait() for p in active))
    sys.argv=[str(HERE/'run_regressions.py'),'--queue',str(effective),'--slots',str(args.slots)]
    asyncio.run(supervised())
    failed=[]
    for job in jobs:
        record=json.loads((out/'evidence/receipts'/(job['name']+'.json')).read_text())
        if record['returncode'] or record['execution']!='FINISHED':failed.append(job['name'])
    emit(out/'status.json',{'passed':not failed,'failed':failed,'jobs':len(jobs),'backend':selected})
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
