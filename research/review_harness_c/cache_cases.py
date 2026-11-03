"""Compiler-cache dependency, flag, environment, and locking checks."""
import concurrent.futures
import contextlib
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, emit, enable, sha

def main():
    enable()
    import content_cache
    base=HERE/'local/cache-cases'
    base.mkdir(parents=True,exist_ok=True)
    header=base/'nested.h';header.write_text('#define REVIEW_VALUE 42\n')
    outer=base/'outer.h';outer.write_text('#include "nested.h"\n')
    source=base/'probe.c'
    source.write_text('#include "outer.h"\n#ifndef REVIEW_ADJUST\n#define REVIEW_ADJUST 0\n#endif\nint probe(void){return REVIEW_VALUE+REVIEW_ADJUST;}\n')
    flags=['-std=c11','-O2','-shared','-fPIC','-I',str(base)]
    cache=content_cache.CommandCache('compile')
    rows=[]
    loaded=[]
    def execute(label,cache_obj=cache,extra=(),enabled=True,src=source):
        path,log,bound=cache_obj.compile('/usr/bin/clang',flags+list(extra),[src],'probe.dylib',enabled)
        # A private filename prevents dlopen from reusing a prior loaded handle.
        copy=base/(label+'.dylib');copy.write_bytes(path.read_bytes())
        library=ctypes.CDLL(str(copy));loaded.append(library)
        library.probe.restype=ctypes.c_int
        value=library.probe()
        row=dict(case=label,value=value,binding=bound,path=str(path),sha256=sha(path),stats=dict(cache_obj.stats))
        rows.append(row)
        return row
    first=execute('initial')
    again=execute('same-input')
    assert first['value']==again['value']==42 and cache.stats['hits']==1
    header.write_text('#define REVIEW_VALUE 43\n')
    changed=execute('nested-header-change')
    assert changed['value']==43 and changed['path']!=first['path']
    changed_flags=execute('flag-change',extra=['-DREVIEW_ADJUST=4'])
    assert changed_flags['value']==47 and changed_flags['path']!=changed['path']
    assert str(header) in first['binding']['dependencies'] and str(outer) in first['binding']['dependencies']
    artifact=Path(changed_flags['path'])
    bytes_=bytearray(artifact.read_bytes());bytes_[-1]^=1;artifact.write_bytes(bytes_)
    repaired=execute('artifact-repair',extra=['-DREVIEW_ADJUST=4'])
    assert repaired['value']==47 and repaired['sha256']==changed_flags['sha256'] and cache.stats['invalid']==1

    concurrent_source=base/'concurrent.c';concurrent_source.write_text('int probe(void){return 42;}\n')
    barrier=threading.Barrier(2)
    subprocess_lock=threading.Lock()
    original_run=subprocess.run
    active=[0,0];actual_compiles=[]
    def serial_subprocess(command,*args,**kwargs):
        with subprocess_lock:
            active[0]+=1;active[1]=max(active)
            if '-o' in command:actual_compiles.append(list(map(str,command)))
            try:return original_run(command,*args,**kwargs)
            finally:active[0]-=1
    class ConcurrentCache(content_cache.CommandCache):
        @contextlib.contextmanager
        def locked(self,key):
            barrier.wait(timeout=60)
            with super().locked(key):yield
    def request(index):
        item=ConcurrentCache('compile')
        path,log,bound=item.compile('/usr/bin/clang',flags,[concurrent_source],'probe.dylib',True)
        library=ctypes.CDLL(str(path));library.probe.restype=ctypes.c_int
        return dict(index=index,value=library.probe(),path=str(path),sha256=sha(path),stats=item.stats)
    subprocess.run=serial_subprocess
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results=list(pool.map(request,(0,1)))
    finally:subprocess.run=original_run
    concurrent_check=dict(results=concurrent_results,actual_compile_count=len(actual_compiles),max_child_processes=active[1])
    concurrent_check['passed']=(all(row['value']==42 for row in concurrent_results) and len(actual_compiles)==1
       and sum(row['stats']['misses'] for row in concurrent_results)==1 and sum(row['stats']['hits'] for row in concurrent_results)==1)

    environment_source=base/'environment.c'
    environment_source.write_text('int probe(void){return __ENVIRONMENT_MAC_OS_X_VERSION_MIN_REQUIRED__;}\n')
    environment_cache=content_cache.CommandCache('compile')
    old=os.environ.get('MACOSX_DEPLOYMENT_TARGET')
    try:
        os.environ['MACOSX_DEPLOYMENT_TARGET']='14.0'
        env_first=execute('environment-14',environment_cache,src=environment_source)
        os.environ['MACOSX_DEPLOYMENT_TARGET']='15.0'
        env_cached=execute('environment-15-cached',environment_cache,src=environment_source)
        env_fresh=execute('environment-15-uncached',environment_cache,enabled=False,src=environment_source)
    finally:
        if old is None:os.environ.pop('MACOSX_DEPLOYMENT_TARGET',None)
        else:os.environ['MACOSX_DEPLOYMENT_TARGET']=old
    environment_check=dict(first=env_first['value'],cached=env_cached['value'],uncached=env_fresh['value'],
         same_key=env_first['path']==env_cached['path'],equivalent=env_cached['value']==env_fresh['value'])
    emit(HERE/'local/cache-summary.json',dict(rows=rows,concurrency=concurrent_check,environment=environment_check))
    print(json.dumps(dict(dependency_and_flags=True,concurrency=concurrent_check['passed'],environment=environment_check)),flush=True)

if __name__=='__main__':main()
