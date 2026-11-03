"""Two complete g150 view groups, including all CPU-store and audit bytes."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha

def records(folder,kind):
    result={}
    for path in sorted((folder/'metadata').glob('*.json')):
        for row in json.loads(path.read_text())[kind]:
            assert row['name'] not in result
            result[row['name']]=row
    return result

def main():
    enable();print(subprocess.check_output(['/bin/df','-h','/Volumes/Workspace'],text=True),end='')
    out=HERE/'local/tapes';out.mkdir(exist_ok=True)
    job=next(j for j in json.loads((HERE/'queue.json').read_text())['jobs'] if j['name']=='group126-50mm-view-reentry')
    runs={}
    for option in ('0','1'):
        name='tape-'+option+'-group126-50mm-view-reentry';folder=HERE/'run/local/tapes'/option
        if folder.exists():raise FileExistsError(folder)
        env=dict(os.environ,GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT=option,GXR_HOST_METRICS_DIR=str(HERE/'run/local/processes'/name),GXR_TAPES_OUTPUT=str(folder),G139_PACKAGE='firmware/package_v38_g150',G139_ENGINE='firmware/engine_v58_g150',REVIEW_JOB=name)
        command=['/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),sys.executable,'-I','-B',str(HERE/'run/tape_launch.py'),name,*job['args']]
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic()
        with (out/(option+'.log')).open('w') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        if result.returncode:raise RuntimeError((out/(option+'.log')).read_text()[-2200:])
        assert len(list((folder/'metadata').glob('*.json')))==71
        processes=[json.loads(p.read_text()) for p in (HERE/'run/local/processes'/name).glob('*.json')]
        packets=sum(p['packets'] for p in processes)
        expected=json.loads((HERE/'local/measurements/c/group126-50mm-view-reentry/measurement.json').read_text())['packets']
        assert packets==expected and packets>0
        runs[option]={'returncode':result.returncode,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'wall_seconds':time.monotonic()-start,'processes':71,'kinds':{kind:records(folder,kind) for kind in ('write','audit')}}
        emit(out/'progress.json',runs);print(json.dumps({'tape_option':option,'wall_seconds':runs[option]['wall_seconds']}),flush=True)
    comparisons={}
    for kind in ('write','audit'):
        a,b=(runs[side]['kinds'][kind] for side in ('0','1'));equal=a==b
        if equal:
            for name in a:
                left=HERE/'run/local/tapes/0'/(kind+'-tapes')/name;right=HERE/'run/local/tapes/1'/(kind+'-tapes')/name
                with left.open('rb') as x,right.open('rb') as y:
                    while True:
                        p,q=x.read(1048576),y.read(1048576)
                        if p!=q:equal=False;break
                        if not p:break
        comparisons[kind]={'equal':equal,'files':len(a),'records':sum(v['records'] for v in a.values()),'bytes':sum(v['bytes'] for v in a.values()),'byte_comparison':True}
        assert equal,kind
    # Omit one actual UI hit in the C library, then replay all 70 children.
    name='tape-mutant-group126-50mm-view-reentry';folder=HERE/'run/local/tapes/mutant'
    manifest=HERE/'local/gates/mutations/omitted-audit-hit/build.json'
    assert manifest.is_file()
    env=dict(os.environ,GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1',GXR_CAPTURE_CPU_TAPES='0',GXR_CCORE_BUILD_MANIFEST=str(manifest),GXR_HOST_METRICS_DIR=str(HERE/'run/local/processes'/name),GXR_TAPES_OUTPUT=str(folder),G139_PACKAGE='firmware/package_v38_g150',G139_ENGINE='firmware/engine_v58_g150',REVIEW_JOB=name)
    command=['/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),sys.executable,'-I','-B',str(HERE/'run/tape_launch.py'),name,*job['args']]
    with (out/'mutation.log').open('w') as stream:mutation=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=10800)
    assert mutation.returncode==0, (out/'mutation.log').read_text()[-2000:]
    bad=records(folder,'audit');good=runs['1']['kinds']['audit'];assert bad!=good
    mutation_proof={'detected':True,'normal_records':sum(v['records'] for v in good.values()),'altered_records':sum(v['records'] for v in bad.values()),'processes':len(list((folder/'metadata').glob('*.json'))),'library_sha256':json.loads(manifest.read_text())['sha256']}
    assert mutation_proof['processes']==71
    emit(out/'mutation.json',mutation_proof)
    emit(out/'summary.json',{'passed':True,'scope':'complete g150 50mm view-reentry, filter off and on, 70 children each','comparisons':comparisons,'runs':runs})
    print(json.dumps({'tapes_passed':True,'comparisons':comparisons}),flush=True)
if __name__=='__main__':main()
