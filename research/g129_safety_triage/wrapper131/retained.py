"""Run a retained entry by path with scoped writes and named version fields."""
from pathlib import Path
import argparse
import ast
import builtins
import contextlib
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import io
import inspect
import json
import os
import re
import shutil
import sys
import types
import time

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(WORK))
import bindings

def imports():
    virtual=ROOT/'firmware/engine_v51_g131'
    base=ROOT/'firmware/engine_v48_own'
    original=importlib.machinery.SourceFileLoader.get_data
    def source(path):
        try: candidate=base/Path(path).relative_to(virtual)
        except ValueError:return None
        return candidate if candidate.suffix=='.py' and candidate.is_file() else None
    def get_data(loader,path):
        patched=os.environ.get('TRIAGE_PATCH_SAFETY')
        if patched and str(path).endswith('review_g124/safety_cases.py'):return Path(patched).read_bytes()
        alternate=source(path)
        return original(loader,str(alternate)) if alternate and not Path(path).exists() else original(loader,path)
    importlib.machinery.SourceFileLoader.get_data=get_data
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            for folder in sys.path if path is None else path:
                candidate=Path(folder)/(fullname.rsplit('.',1)[-1]+'.py')
                if not candidate.exists() and source(candidate):
                    return importlib.util.spec_from_file_location(fullname,str(candidate),
                        loader=importlib.machinery.SourceFileLoader(fullname,str(candidate)))
            return None
    sys.meta_path.insert(0,Finder())

class RunnerShape(ast.NodeTransformer):
    def __init__(self,job):self.job=job
    def visit_FunctionDef(self,node):
        if node.name=='target_code':
            return ast.copy_location(ast.parse('def target_code(code, source_generation=None, target_generation=131):\n return safe_bind(code, source_generation, target_generation)\n').body[0],node)
        node=self.generic_visit(node)
        if node.name=='adjust':node.body.append(ast.parse('safe_adjust(module)').body[0])
        if node.name=='capture_setup':
            node.body.insert(0,ast.parse('safe_setup(original_setup)').body[0])
            node.body.insert(0,ast.parse("if a and type(a[0]) is int and a[0] in (122,123,124,126,127):\n a=(131,)+a[1:]\n").body[0])
        if node.name=='start_process':
            node.body.insert(len(node.body)-1,ast.parse('command=safe_command(command)').body[0])
        if node.name=='open_io':
            node.body.insert(len(node.body)-1,ast.parse("if any(c in mode for c in 'wax+') and isinstance(getattr(kw.get('opener'),'__self__',None),Path):\n kw.pop('opener')\n").body[0])
        return node
    def visit_Assign(self,node):
        node=self.generic_visit(node)
        if any(isinstance(t,ast.Name) and t.id=='a' for t in node.targets) and isinstance(node.value,ast.BinOp):
            first=node.value.left
            if isinstance(first,ast.Tuple) and first.elts and isinstance(first.elts[0],ast.Constant) and first.elts[0].value==127:first.elts[0]=ast.Constant(131)
        return node
    def visit_Constant(self,node):
        replacements={'research/g127_fix':'research/g129_safety_triage/wrapper131',
                      'firmware/engine_v48_own':'firmware/engine_v51_g131',
                      'firmware/package_v36_g127':'firmware/package_v36_g131',
                      'g127_fix':'g129_safety_triage','local/release127':'local/'+self.job}
        if isinstance(node.value,str) and node.value in replacements:
            return ast.copy_location(ast.Constant(replacements[node.value]),node)
        return node
    def visit_Dict(self,node):
        node=self.generic_visit(node)
        for index,key in enumerate(node.keys):
            if isinstance(key,ast.Constant) and key.value=='generation':
                value=node.values[index]
                if isinstance(value,ast.Constant) and value.value==127:node.values[index]=ast.Constant(131)
        return node

def main():
    started=time.time()
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--job',required=True)
    parser.add_argument('--crc-mode',choices=('host','native'),default='host')
    parser.add_argument('--self-check',action='store_true')
    parser.add_argument('--probe-ui',action='store_true')
    parser.add_argument('--probe-failure',action='store_true')
    parser.add_argument('--probe-math',action='store_true')
    parser.add_argument('--probe-legacy',action='store_true')
    parser.add_argument('--probe-unit',choices=('50mm','28mm','mount'),default='50mm')
    args,tail=parser.parse_known_args()
    if args.self_check:
        print(json.dumps(bindings.self_check()));return
    assert tail and all(char.isalnum() or char in '-_' for char in args.job)
    folder=WORK/'local'/args.job;folder.mkdir(parents=True,exist_ok=True)
    layout=WORK/'local/focus-layout/review_g126/local/layout'
    if layout.is_dir():
        for family in ('review_g122','review_g123','review_g124','review_g126','review_g127'):
            destination=folder/family/'local/layout'
            if destination!=layout:shutil.copytree(layout,destination,dirs_exist_ok=True)
    os.environ.update(TMPDIR=str(WORK/'local/tmp'),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0')
    imports();bindings.JOB=args.job
    wrapper_hashes={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in
                    ('retained.py','bindings.py','ui_adapter.py','r2_oracle.py','product_post.py','legacy_cases.py','legacy_model.py','write_failure.py')}
    original_argument=argparse.ArgumentParser.add_argument
    schemas=[]
    def argument(self,*names,**kw):
        if '--generation' in names:
            if 'default' in kw:kw['default']=131
            if 'choices' in kw and 131 not in kw['choices']:kw['choices']=list(kw['choices'])+[131]
        result=original_argument(self,*names,**kw)
        schemas.append({'dest':result.dest,'options':result.option_strings,'nargs':result.nargs})
        return result
    argparse.ArgumentParser.add_argument=argument
    path=ROOT/'research/g127_fix/run_existing.py'
    tree=RunnerShape(args.job).visit(ast.parse(path.read_text(),filename=str(path)))
    ast.fix_missing_locations(tree)
    sys.argv=[str(path)]+(['--fast-crc'] if args.crc_mode=='native' else [])+tail
    child_count=0
    def child_command(command):
        nonlocal child_count
        if isinstance(command,(tuple,list)):
            command=list(command)
            for index,value in enumerate(command):
                if str(value)==str(path):
                    child_count+=1;rest=command[index+1:]
                    mode='native' if '--fast-crc' in rest else 'host'
                    rest=[value for value in rest if value!='--fast-crc']
                    command=['/usr/bin/python3','-I','-B',str(WORK/'retained.py'),'--job',args.job+'-child-'+str(child_count),'--crc-mode',mode,*rest]
                    break
        return command
    environment={'__name__':'__main__','__file__':str(path),'safe_bind':bindings.bind,'safe_adjust':bindings.adjust,'safe_setup':bindings.setup_function,'safe_command':child_command}
    saved_io=io.open;saved_open=builtins.open;saved_mkdir=Path.mkdir
    stream=io.StringIO();status=0;error_name=None;own_frames=[];own_reason=None
    original_exit=os._exit
    def child_exit(code):
        names=[]
        for line in stream.getvalue().splitlines():
            match=re.search(r'File "([^"]+)", line (\d+), in (\S+)',line)
            if match:names.append(Path(match.group(1)).parent.name+'/'+Path(match.group(1)).name+':'+match.group(3)+':'+match.group(2))
        report=Path(environment.get('OUT',folder))/('child-result-'+str(os.getpid())+'.json')
        report.write_text(json.dumps({'name':args.job,'returncode':code,'failure_names':names,'captured_lines':len(stream.getvalue().splitlines())},indent=2)+'\n')
        original_exit(code)
    os._exit=child_exit
    dat=ROOT/'firmware/package_v36_g131/SD_ROOT/GXRCE.DAT'
    before=hashlib.sha256(dat.read_bytes()).hexdigest()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            exec(compile(tree,str(path),'exec'),environment)
            if args.probe_ui or args.probe_failure or args.probe_math or args.probe_legacy:
                import ui_adapter
                helper=types.SimpleNamespace(**environment['env'])
                ui_adapter.install(helper)
                options={'unit':args.probe_unit,'tag':'field-probe'}
                if args.probe_legacy:
                    import legacy_model
                    options['dat']=legacy_model.fixture(helper.OUT)
                session=helper.Session(**options)
                state=session.state()
                assert len(state['labels'])==8
                if args.probe_math:session.match()
                if args.probe_legacy:legacy_model.verify(session,helper.OUT)
                if args.probe_failure:
                    import write_failure
                    write_failure.run(session,helper.OUT)
        except SystemExit as error:status=error.code or 0
        except BaseException as error:
            status=1;error_name=type(error).__name__
            cursor=error.__traceback__
            while cursor:
                code=cursor.tb_frame.f_code;own_frames.append(Path(code.co_filename).parent.name+'/'+Path(code.co_filename).name+':'+code.co_name+':'+str(cursor.tb_lineno));cursor=cursor.tb_next
            if error_name!='AssertionError':own_reason=str(error)[:240]
    io.open=saved_io;builtins.open=saved_open;Path.mkdir=saved_mkdir
    assert hashlib.sha256(dat.read_bytes()).hexdigest()==before
    result={'name':args.job,'returncode':status,'dat_sha256':before,
            'captured_lines':len(stream.getvalue().splitlines()),'crc_mode':args.crc_mode,
            'generation_bindings':len(bindings.RECORDS)}
    result['seconds']=round(time.time()-started,3)
    result['wrapper_hashes_at_start']=wrapper_hashes
    if error_name:
        result.update(error_type=error_name,failure_names=own_frames)
        if own_reason:result['reason']=own_reason
    for line in stream.getvalue().splitlines():
        try:item=json.loads(line)
        except ValueError:continue
        if isinstance(item,dict) and 'error' in item:
            result['error_type']=item['error']
            result['failure_names']=[Path(f['file']).parent.name+'/'+Path(f['file']).name+':'+f['function']+':'+str(f['line']) for f in item.get('frames',[])]
            if item['error']!='AssertionError':result['reason']=str(item.get('message',''))[:400]
            result['detail_names']=list(item.get('details',{}))
            result['state_counts']={key:value for key,value in item.get('details',{}).items()
                                    if type(value) in (int,bool)}
            if 'unit' in item.get('details',{}):result['unit_name']=item['details']['unit']
    report_folder=Path(environment.get('OUT',folder))
    target_environment=environment.get('env',{})
    if any(Path(value).name=='ui_test_support.py' for value in tail if value.endswith('.py')):
        contracts={}
        for name,value in target_environment.items():
            if inspect.isfunction(value):
                fields=[]
                for constant in value.__code__.co_consts:
                    candidates=constant if isinstance(constant,tuple) else (constant,)
                    fields.extend(v for v in candidates if isinstance(v,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',v))
                contracts[name]={'parameters':str(inspect.signature(value)),'names':list(value.__code__.co_names),'fields':fields,'file_name':Path(value.__code__.co_filename).name}
        contracts['_environment_names']=list(target_environment)
        for class_name,klass in target_environment.items():
            if not inspect.isclass(klass) or class_name not in ('Session','Algorithm'):continue
            for method_name,method in vars(klass).items():
                if not inspect.isfunction(method):continue
                fields=[]
                for constant in method.__code__.co_consts:
                    candidates=constant if isinstance(constant,tuple) else (constant,)
                    fields.extend(v for v in candidates if isinstance(v,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',v))
                contracts[class_name+'.'+method_name]={'parameters':str(inspect.signature(method)),'names':list(method.__code__.co_names),'fields':fields}
                if class_name=='Session' and method_name=='state':contracts[class_name+'.'+method_name]['hardware_constants']=[v for v in method.__code__.co_consts if type(v) is int and 0x20000000<=v<0x21000000]
        (report_folder/'helper-contracts.json').write_text(json.dumps(contracts,indent=2)+'\n')
    (report_folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (report_folder/'bindings.json').write_text(json.dumps(bindings.RECORDS,indent=2)+'\n')
    (report_folder/'registries.json').write_text(json.dumps(bindings.REGISTRIES,indent=2)+'\n')
    if '--help' in tail:(report_folder/'cli.json').write_text(json.dumps(schemas,indent=2)+'\n')
    print(json.dumps(result));raise SystemExit(status)

if __name__=='__main__':main()
