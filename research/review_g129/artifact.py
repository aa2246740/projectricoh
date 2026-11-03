"""Repeat integrated host or target checks with all outputs in this review."""
from pathlib import Path
import argparse
import builtins
import contextlib
import hashlib
import io
import json
import os
import runpy
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=('host','target'))
    parser.add_argument('--unit',type=int,default=0)
    args=parser.parse_args()
    destination=WORK/'local'/('integrated-host' if args.kind=='host' else f'integrated-target-{args.unit}')
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'local').mkdir(exist_ok=True)
    original=ROOT/'research/g129_knobs'
    case_sha=None
    if args.kind=='target':
        unit=('50mm','28mm','mount')[args.unit]
        job={'50mm':'focus-product-50mm','28mm':'focus-product-28mm-r17','mount':'focus-product-mount'}[unit]
        source=WORK/'local'/job/'review_g126'/f'target-state-{unit}-0'
        fresh=WORK/'local/integrated-host/local'/f'target-cases-{args.unit}.bin'
        retained=original/'local'/f'target-cases-{args.unit}.bin'
        case_sha=hashlib.sha256(fresh.read_bytes()).hexdigest()
        assert case_sha==hashlib.sha256(retained.read_bytes()).hexdigest(),'target cases differ from the fresh host reference'
        state=destination/'state'
        shutil.copytree(source,state,dirs_exist_ok=True)
    sys.path.insert(0,str(original))
    loaded=runpy.run_path(str(original/('host_check.py' if args.kind=='host' else 'target_check.py')))
    namespace=loaded['main'].__globals__
    namespace['LOCAL']=destination/args.kind
    namespace['enable']=lambda:None
    old_io=io.open;old_open=builtins.open;old_mkdir=Path.mkdir
    def mapped(value):
        if isinstance(value,int):return value
        try:return destination/Path(value).relative_to(original)
        except (ValueError,TypeError):return value
    def open_io(path,mode='r',*a,**kw):
        if any(char in mode for char in 'wax+'):
            path=mapped(path)
            if isinstance(getattr(kw.get('opener'),'__self__',None),Path):kw.pop('opener')
        return old_io(path,mode,*a,**kw)
    def open_builtin(path,mode='r',*a,**kw):
        if any(char in mode for char in 'wax+'):
            path=mapped(path)
            if isinstance(getattr(kw.get('opener'),'__self__',None),Path):kw.pop('opener')
        return old_open(path,mode,*a,**kw)
    def mkdir(path,*a,**kw):return old_mkdir(Path(mapped(path)),*a,**kw)
    io.open=open_io;builtins.open=open_builtin;Path.mkdir=mkdir
    os.environ.update(TMPDIR=str(WORK/'local/tmp'),PYTHONDONTWRITEBYTECODE='1')
    sys.argv=[str(original/('host_check.py' if args.kind=='host' else 'target_check.py'))]
    if args.kind=='target':sys.argv+=['--state',str(state),'--unit',str(args.unit)]
    output=io.StringIO();status=0;error_name=None
    failure_names=[]
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
        try:loaded['main']()
        except BaseException as error:
            status=1;error_name=type(error).__name__;trace=error.__traceback__
            while trace:
                failure_names.append(Path(trace.tb_frame.f_code.co_filename).name+':'+trace.tb_frame.f_code.co_name+':'+str(trace.tb_lineno));trace=trace.tb_next
    io.open=old_io;builtins.open=old_open;Path.mkdir=old_mkdir
    result={'name':args.kind,'unit':args.unit,'returncode':status,
            'captured_lines':len(output.getvalue().splitlines()),'error_type':error_name,'failure_names':failure_names,
            'cases_sha256':case_sha}
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));raise SystemExit(status)

if __name__=='__main__':main()
