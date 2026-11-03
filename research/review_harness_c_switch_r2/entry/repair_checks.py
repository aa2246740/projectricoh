"""Run retained checks and the review counterexamples serially before measurement."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha

def main():
    enable();out=HERE/'local/repair-checks';out.mkdir(parents=True,exist_ok=True);rows=[]
    manifest=ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json'
    def run(label,script,*args,expected=0,extra=None,timeout=10800):
        env=dict(os.environ,GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1',GXR_CCORE_BUILD_MANIFEST=str(manifest),GXR_R4_CASE_OUTPUT=str(out))
        env.update(extra or {})
        command=['/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),sys.executable,'-I','-B',str(script),*args]
        before=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'case':label,'returncode':result.returncode,'expected':expected,'wall_seconds':time.monotonic()-started,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'command':command,'load_end':os.getloadavg()}
        rows.append(row);emit(out/'progress.json',rows);print(json.dumps(row),flush=True)
        if result.returncode!=expected:
            print((out/(label+'.log')).read_text()[-2400:]);raise RuntimeError(label+' had an unexpected result')
    run('identity-driver',HERE/'identity_cases.py','--phase','after','--form','driver','--tag','final-driver')
    run('retained-gates',HERE/'validate.py')
    for script in ('resolution_globals','event_validation','audit_warm'):
        run(script,HERE/'review_cases'/(script+'.py'))
    run('constructor-and-warm-events',HERE/'event_cases.py')
    run('errors',HERE/'review_cases/error_equivalence.py',expected=1)
    errors=json.loads((out/'errors/summary.json').read_text())
    assert errors['cases']==23 and errors['mismatches']==3
    assert {row['case'] for row in errors['checks'] if not row['equal']}=={'write-trace-negative-low','write-trace-large-high','write-trace-negative-unused'}
    run('switch-controls',HERE/'review_cases/switch_checks.py')
    mutation=out/'omitted-event-binding';mutation.mkdir(exist_ok=True)
    record=json.loads(manifest.read_text());command=list(record['command']);command.insert(1,'-DGXR_TEST_SKIP_EVENT_BINDING=1');command[-1]=str(mutation/Path(record['library']).name)
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=3600)
    (mutation/'build.log').write_bytes(compiled.stdout+compiled.stderr);assert compiled.returncode==0
    record.update(command=command,library=command[-1],sha256=sha(Path(command[-1])));emit(mutation/'build.json',record)
    for script in ('resolution_globals','event_validation'):
        run('mutation-'+script,HERE/'review_cases'/(script+'.py'),expected=1,extra={'GXR_CCORE_BUILD_MANIFEST':str(mutation/'build.json'),'GXR_R4_CASE_OUTPUT':str(mutation)})
    run('busy-full-reporter',HERE/'busy_check.py')
    emit(out/'summary.json',{'passed':True,'library_sha256':json.loads(manifest.read_text())['sha256'],'checks':rows})
    print(json.dumps({'passed':True,'checks':len(rows)}),flush=True)
if __name__=='__main__':main()
