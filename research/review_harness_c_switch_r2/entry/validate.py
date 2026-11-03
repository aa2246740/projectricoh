"""Foreground API6, exact audit predicate, and real omitted-hit mutation checks."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha

def main():
    enable();out=HERE/'local/gates';out.mkdir(exist_ok=True)
    normal=ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json'
    results={}
    def run(name,args,extra=None,expected=0,timeout=3600):
        env=dict(os.environ,GXR_HARNESS_BACKEND='c',GXR_HARNESS_UI_AUDIT='1',GXR_CCORE_BUILD_MANIFEST=str(normal),GXR_REVIEW_FIX_OUTPUT=str(out/'cases'))
        env.update(extra or {})
        command=['/usr/bin/sandbox-exec','-f',str(HERE/'offline.sb'),sys.executable,'-I','-B',*map(str,args)]
        before=resource.getrusage(resource.RUSAGE_CHILDREN);started=time.monotonic()
        with (out/(name+'.log')).open('w') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        row={'returncode':result.returncode,'wall_seconds':time.monotonic()-started,'cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'command':command,'library_manifest':env['GXR_CCORE_BUILD_MANIFEST'],'load_end':os.getloadavg()}
        results[name]=row;emit(out/'progress.json',results)
        print(json.dumps({'name':name,**{k:row[k] for k in ('returncode','wall_seconds','cpu_seconds')}}),flush=True)
        if expected==0 and result.returncode:print((out/(name+'.log')).read_text()[-2200:]);raise RuntimeError(name+' failed')
        if expected!=0 and not result.returncode:raise RuntimeError(name+' did not reject the mutation')
    for name in ('independent_cases','extended_cases','new_cases','trace_cases','mro_cases'):
        run(name,[HERE/'cases'/(name+'.py')],timeout=1800)
    for name,count in [('independent',15),('extended',4),('new',6),('trace',6),('mro',19)]:
        v=json.loads((out/'cases/local'/(name+'-summary.json')).read_text());assert v['cases']==count and v.get('mismatches',0)==0 and v.get('passed',True)
    run('differential',[HERE/'gate_adapter.py','differential','--folder','differential','--repeats','64'])
    v=json.loads((out/'differential/summary.json').read_text());assert v['instruction_cases']==6080 and len(v['boundary_cases'])==40 and v['failures']==0
    run('audit-boundaries',[HERE/'gate_adapter.py','audit'])
    v=json.loads((out/'round2/audit-checks/summary.json').read_text());assert v['passed'] and v['cases']>80
    run('audit-runtime-changes',[HERE/'audit_changes.py'])
    for label,flag in [('omitted-audit-hit','GXR_TEST_DROP_AUDIT_HIT'),('omitted-method-guard','GXR_TEST_SKIP_METHOD_GUARD')]:
        folder=out/'mutations'/label;folder.mkdir(parents=True,exist_ok=True)
        record=json.loads(normal.read_text());command=list(record['command']);command.insert(1,'-D'+flag+'=1');command[-1]=str(folder/Path(record['library']).name)
        result=subprocess.run(command,capture_output=True,text=True,timeout=3600)
        (folder/'build.log').write_text(result.stdout+result.stderr);assert result.returncode==0
        record.update(library=command[-1],sha256=sha(Path(command[-1])),command=command);emit(folder/'build.json',record)
        extra={'GXR_CCORE_BUILD_MANIFEST':str(folder/'build.json'),'GXR_GATE_OUTPUT':str(folder),'GXR_REVIEW_FIX_OUTPUT':str(folder/'cases')}
        if label=='omitted-audit-hit':
            run(label,[HERE/'gate_adapter.py','audit'],extra,expected=1)
            v=json.loads((folder/'round2/audit-checks/summary.json').read_text());assert not v['passed']
        else:
            run(label,[HERE/'cases/new_cases.py'],extra)
            v=json.loads((folder/'cases/local/new-summary.json').read_text());assert v['mismatches']==2
    emit(out/'summary.json',{'passed':True,'api':6,'library_sha256':json.loads(normal.read_text())['sha256'],'results':results})
if __name__=='__main__':main()
