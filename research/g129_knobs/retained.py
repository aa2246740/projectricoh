"""Call retained checks by path with generation and output rebinding."""
from pathlib import Path
import contextlib
import argparse
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import types
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,check_inputs,enable

VIRTUAL=ROOT/'firmware/engine_v49_knobs'
BASE=ROOT/'firmware/engine_v48_own'

def original_source(path):
    try:relative=Path(path).relative_to(VIRTUAL)
    except ValueError:return None
    candidate=BASE/relative
    return candidate if candidate.suffix=='.py' and candidate.is_file() else None

def retained_imports():
    original=importlib.machinery.SourceFileLoader.get_data
    execute_original=importlib.machinery.SourceFileLoader.exec_module
    def get_data(loader,path):
        source=original_source(path)
        return original(loader,str(source)) if source and not Path(path).exists() else original(loader,path)
    importlib.machinery.SourceFileLoader.get_data=get_data
    process_original=subprocess.Popen.__init__
    def guarded_process(self,*a,**kw):
        if os.environ.get('G129_CACHE_ONLY')=='1':raise RuntimeError('CACHE_REQUIRED: child process disabled')
        return process_original(self,*a,**kw)
    subprocess.Popen.__init__=guarded_process
    def execute(loader,module):
        execute_original(loader,module)
        core=getattr(module,'Core',None);backend=getattr(module,'PythonBackend',None)
        if core is None or backend is None or getattr(core,'g129_measured',False):return
        operation=core.op;call=backend.call
        def measured_operation(self,*args,**kw):
            result=operation(self,*args,**kw)
            value=self.r[15]
            if hasattr(self.owner,'g129_stack_min') and value<self.owner.g129_stack_min:self.owner.g129_stack_min=value
            return result
        def measured_call(self,address,*args,**kw):
            initial=self.get_reg('r15');self.g129_stack_min=initial
            result=call(self,address,*args,**kw)
            if not hasattr(self,'g129_stack_calls'):self.g129_stack_calls=[]
            self.g129_stack_calls.append({'entry':address,'initial_sp':initial,'minimum_sp':self.g129_stack_min,
                                         'stack_bytes':initial-self.g129_stack_min})
            return result
        core.op=measured_operation;core.g129_measured=True;backend.call=measured_call
    importlib.machinery.SourceFileLoader.exec_module=execute
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            for folder in sys.path if path is None else path:
                virtual=Path(folder)/(fullname.rsplit('.',1)[-1]+'.py')
                if not virtual.exists() and original_source(virtual):
                    return importlib.util.spec_from_file_location(fullname,str(virtual),
                        loader=importlib.machinery.SourceFileLoader(fullname,str(virtual)))
            return None
    sys.meta_path.insert(0,Finder())

def bind(code):
    def value(item):
        if isinstance(item,types.CodeType):return bind(item)
        if type(item) is int and item==127:return 129
        if isinstance(item,tuple):return tuple(value(x) for x in item)
        if isinstance(item,frozenset):return frozenset(value(x) for x in item)
        if isinstance(item,str):
            for old,new in [('engine_v48_own','engine_v49_knobs'),('package_v36_g127','package_v36_g129'),
                            ('research/g127_fix','research/g129_knobs'),('release127',os.environ.get('G129_RUN_DIR','release129')),('g127_fix','g129_knobs')]:
                item=item.replace(old,new)
        return item
    return code.replace(co_consts=tuple(value(item) for item in code.co_consts))

def main():
    enable();before=check_inputs();retained_imports()
    dat=ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT'
    dat_sha=hashlib.sha256(dat.read_bytes()).hexdigest() if dat.exists() else None
    runner=ROOT/'research/g127_fix/run_existing.py'
    args=sys.argv[1:]
    if (WORK/'local/menu-batch-moved').exists() and not os.environ.get('G129_RUN_DIR') and \
       'research/g129_knobs/product_after_owner.py' in args and '--unit' in args and args[args.index('--unit')+1] in ('28mm','mount'):
        print(json.dumps({'name':'menu_batch_moved','returncode':75,'count':1}));raise SystemExit(75)
    with_cold='--with-cold' in args
    if with_cold:args.remove('--with-cold')
    script_arg=next(x for i,x in enumerate(args) if x.endswith('.py') and (i==0 or args[i-1]!='--postcheck'))
    name=Path(script_arg).name
    stream=io.StringIO();status=0;error_type=None
    schemas=[];original_parse=argparse.ArgumentParser.parse_known_args
    def describe_parse(parser,*a,**kw):
        schemas.append([{'dest':item.dest,'options':item.option_strings,'nargs':item.nargs,'required':item.required}
                        for item in parser._actions])
        return original_parse(parser,*a,**kw)
    if '--help' in args:argparse.ArgumentParser.parse_known_args=describe_parse
    sys.argv=[str(runner)]+args
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            loader=importlib.machinery.SourceFileLoader('g129_retained_runner',str(runner))
            environment={'__name__':'__main__','__file__':str(runner)}
            exec(bind(loader.get_code('g129_retained_runner')),environment)
        except SystemExit as error:status=error.code or 0
        except BaseException as error:status=1;error_type=type(error).__name__
    count=check_inputs();assert count==before
    assert dat_sha is None or hashlib.sha256(dat.read_bytes()).hexdigest()==dat_sha,'STOP_CANDIDATE_CHANGED'
    result={'name':name,'returncode':status,'captured_lines':len(stream.getvalue().splitlines()),'frozen_inputs':count,'dat_sha256':dat_sha}
    if error_type:result['error_type']=error_type
    script=ROOT/script_arg
    out=WORK/'local'/os.environ.get('G129_RUN_DIR','release129')/script.parent.name;out.mkdir(parents=True,exist_ok=True)
    tag=name[:-3]+'-'+('-'.join(args[args.index(script_arg)+1:]).replace('/','_') or 'default')
    (out/(tag+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    if status:
        for line in stream.getvalue().splitlines():
            try:detail=json.loads(line)
            except ValueError:continue
            if isinstance(detail,dict) and 'error' in detail:
                names=[Path(frame['file']).name+':'+frame['function']+':'+str(frame['line']) for frame in detail.get('frames',[])]
                result['failure_names']=names;result['error_type']=detail['error']
                if detail['error']!='AssertionError':result['reason']=detail.get('message','')
                (out/(tag+'-diagnostic.json')).write_text(json.dumps(detail,indent=2)+'\n')
    (out/(tag+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    if '--help' in args:
        import re
        (out/(name[:-3]+'-options.json')).write_text(json.dumps(sorted(set(re.findall(r'--[a-z][a-z-]*',stream.getvalue()))),indent=2)+'\n')
        (out/(name[:-3]+'-cli.json')).write_text(json.dumps(schemas,indent=2)+'\n')
    print(json.dumps(result))
    if with_cold and not status:
        cold=ROOT/'research/review_g126/cold_reentry.py';tail=args[args.index(script_arg)+1:]
        sys.argv=[str(cold)]+tail;cold_status=0
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            try:
                cold_loader=importlib.machinery.SourceFileLoader('g129_cold',str(cold))
                exec(environment['target_code'](cold_loader.get_code('g129_cold')),
                     {'__name__':'__main__','__file__':str(cold),'__package__':None})
            except SystemExit as error:cold_status=error.code or 0
            except BaseException as error:
                cold_status=1
                (out/('cold-'+tail[-1]+'-diagnostic.json')).write_text(json.dumps({'type':type(error).__name__,'message':str(error)},indent=2)+'\n')
        result={'name':'cold_reentry.py','returncode':cold_status,'dat_sha256':dat_sha,'frozen_inputs':check_inputs()}
        tag='cold_reentry-'+('-'.join(tail) or 'default')
        (out/(tag+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));status=cold_status
    raise SystemExit(status)

if __name__=='__main__':main()
