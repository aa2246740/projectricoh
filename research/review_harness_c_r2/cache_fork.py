"""Use one inherited cache in a fork child after changing its environment."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, emit, enable

def main():
    enable()
    import content_cache
    base=HERE/'local/cache-fork'
    base.mkdir(parents=True,exist_ok=True)
    source=base/'environment.c'
    source.write_text('int probe(void){return __ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__;}\n')
    cache=content_cache.CommandCache('compile')
    flags=['-std=c11','-O2','-shared','-fPIC']
    libraries=[]
    def request(label,cache_obj=cache,enabled=True):
        path,_,bound=cache_obj.compile('/usr/bin/clang',flags,[source],'probe.dylib',enabled)
        private=base/(label+'.dylib');private.write_bytes(path.read_bytes())
        library=ctypes.CDLL(str(private));libraries.append(library)
        library.probe.restype=ctypes.c_int
        return dict(value=library.probe(),path=str(path),tool_environment=bound['tool']['environment'],
                    environment_sha256=bound['tool']['environment_sha256'],stats=dict(cache_obj.stats))
    os.environ['MACOSX_DEPLOYMENT_TARGET']='14.0'
    before=request('parent-14')
    original_run=subprocess.run
    responses={}
    def recorded_run(command,*args,**kwargs):
        result=original_run(command,*args,**kwargs)
        responses[tuple(map(str,command))]=result
        return result
    os.environ['MACOSX_DEPLOYMENT_TARGET']='15.0'
    subprocess.run=recorded_run
    try:
        primed=request('prime-15',content_cache.CommandCache('compile'))
    finally:subprocess.run=original_run
    os.environ['MACOSX_DEPLOYMENT_TARGET']='14.0'
    parent=os.getpid()
    child=os.fork()
    if child==0:
        signal.setitimer(signal.ITIMER_REAL,1800)
        os.environ['MACOSX_DEPLOYMENT_TARGET']='15.0'
        replayed=[]
        def replay_run(command,*args,**kwargs):
            command=tuple(map(str,command))
            if '-o' in command:raise AssertionError('child cache lookup must use the primed real artifact')
            assert kwargs['env']['MACOSX_DEPLOYMENT_TARGET']=='15.0'
            replayed.append(list(command))
            return responses[command]
        subprocess.run=replay_run
        try:
            after=request('child-15-cached')
            emit(base/'child.json',dict(pid=os.getpid(),result=after,replayed_commands=replayed))
            status=0
        except BaseException as error:
            emit(base/'child.json',dict(pid=os.getpid(),error=repr(error)));status=1
        os._exit(status)
    waited,status=os.waitpid(child,0)
    assert waited==child and status==0
    child_record=json.loads((base/'child.json').read_text());after=child_record['result']
    os.environ['MACOSX_DEPLOYMENT_TARGET']='15.0'
    direct=request('parent-15-uncached',enabled=False)
    passed=(parent!=child and before['value']==140000 and after['value']==direct['value']==primed['value']==150000
        and before['path']!=after['path'] and before['environment_sha256']!=after['environment_sha256'])
    emit(HERE/'local/cache-fork-summary.json',dict(passed=passed,parent_pid=parent,child_pid=child,
         inherited_cache_object=True,max_review_processes_during_fork=2,before=before,after=after,direct=direct,primed=primed,
         child_tools='exact recorded tool and dependency responses from the real 15.0 compilation; child hit opens that real library',
         replayed_commands=child_record['replayed_commands']))
    print(json.dumps(dict(passed=passed,parent_pid=parent,child_pid=child,values=[before['value'],after['value'],direct['value']])),flush=True)
    assert passed

if __name__=='__main__':main()
