"""Call an existing suite by its original path, within the output fence."""
from pathlib import Path
import builtins
import inspect
import contextlib
import io
import json
import os
import runpy
import sys
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUTPUTS=(HERE, ROOT/'firmware/engine_diag_v2', ROOT/'firmware/package_v36_diag2')
MAPPINGS=((ROOT/'research/diag_dat_v1',HERE/'local/legacy/v1'),
          (ROOT/'research/review_diag',HERE/'local/legacy/review'),
          (ROOT/'firmware/engine_diag_v1',ROOT/'firmware/engine_diag_v2'),
          (ROOT/'firmware/package_v36_diag1',ROOT/'firmware/package_v36_diag2'))

def mapped(p):
    for source,dest in MAPPINGS:
        if p==source or source in p.parents:return dest/p.relative_to(source)
    return p

def mapped_value(v,depth=0):
    if isinstance(v,Path):return mapped(v)
    if depth>4:return v
    if isinstance(v,tuple):return tuple(mapped_value(x,depth+1) for x in v)
    if isinstance(v,list):return [mapped_value(x,depth+1) for x in v]
    if isinstance(v,set):return {mapped_value(x,depth+1) for x in v}
    if isinstance(v,dict):return {k:mapped_value(x,depth+1) for k,x in v.items()}
    return v

def adapt(namespace):
    spaces=[namespace]
    spaces.extend(m.__dict__ for m in list(sys.modules.values())
        if getattr(m,'__file__','') and str(ROOT) in str(getattr(m,'__file__',''))
        and m.__dict__ is not globals())
    for v in list(namespace.values()):
        if inspect.isfunction(v):spaces.append(v.__globals__)
        elif inspect.isclass(v) and v.__module__!='pathlib':
            spaces.extend(f.__globals__ for f in v.__dict__.values() if inspect.isfunction(f))
    seen=set()
    for space in spaces:
        if id(space) in seen:continue
        seen.add(id(space))
        for k,v in list(space.items()):
            if not k.startswith('__'):space[k]=mapped_value(v)
        if space.get('__name__')=='python_backend':space['CACHE']=HERE/'local/decode'
        if space.get('__name__')=='product_execute':
            space['STAGED_SHA']=space['hashlib'].sha256(space['STAGED'].read_bytes()).hexdigest()
    for p in (HERE/'local/legacy/v1',HERE/'local/legacy/review',HERE/'local/decode'):
        p.mkdir(parents=True,exist_ok=True)
    layout=HERE/'local/legacy/v1/layout.json'
    if not layout.exists():layout.write_bytes((ROOT/'research/diag_dat_v1/layout.json').read_bytes())

def load_path(path):
    existing=sys.modules.get('scope')
    if existing is not None and getattr(existing,'__file__','')==str(HERE/'scope.py'):
        sys.modules.pop('scope')
    sys.path.insert(0,str(ROOT/'research/diag_dat_v1'))
    sys.path.insert(0,str(path.parent))
    add=sys.addaudithook
    # The active fence above covers exactly this task's three directories.
    # Old modules may register a fence naming their original output folders.
    sys.addaudithook=lambda hook: None
    try:namespace=runpy.run_path(str(path),run_name='legacy_path_metadata')
    finally:sys.addaudithook=add
    adapt(namespace)
    return namespace

def fence(event,args):
    path=None
    if event=='open':
        path,mode,flags=args
        if isinstance(path,int) or not (flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            return
    elif event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.chmod','os.utime'):
        path=args[0]
    if path is not None:
        p=Path(path).absolute()
        if not any(p==d or d in p.parents for d in OUTPUTS):
            raise RuntimeError('WRITE_FENCE:'+str(p.relative_to(ROOT) if ROOT in p.parents else p))

def main():
    path=ROOT/sys.argv[1]
    sys.addaudithook(fence)
    namespace=load_path(path)
    if '--function' in sys.argv:
        at=sys.argv.index('--function');name=sys.argv[at+1]
        args=json.loads(sys.argv[at+2])
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            value=namespace[name](*args)
        if name=='setup':
            h,p=value[:2]
            print('SETUP RETURN 0 COUNT',len(value),'CLASS',type(p).__name__)
        else:print(path.name,'RETURN 0 COUNT',len(value) if isinstance(value,(dict,list,tuple)) else 1)
        return
    info={}
    for k,v in namespace.items():
        if isinstance(v,Path):info[k]=str(v)
        elif inspect.isfunction(v) and v.__module__=='legacy_path_metadata':info[k]=str(inspect.signature(v))
        elif inspect.isclass(v):info[k]='class '+str(inspect.signature(v))
        elif inspect.ismodule(v) and getattr(v,'__file__',None):info[k]=v.__file__
    print(json.dumps(info,indent=2))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('LEGACY_CALL RETURN 1 TYPE',type(e).__name__)
        frames=[];tb=e.__traceback__
        while tb:
            frames.append((Path(tb.tb_frame.f_code.co_filename).name,tb.tb_frame.f_code.co_name,tb.tb_lineno))
            tb=tb.tb_next
        print('FRAME_NAMES',json.dumps(frames))
        if not isinstance(e,AssertionError):print('DETAIL',str(e)[:500])
        raise SystemExit(1)
