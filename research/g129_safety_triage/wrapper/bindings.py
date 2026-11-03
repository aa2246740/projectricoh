"""Bind version names and fields while retaining numeric domain limits."""
from pathlib import Path
import dis
import hashlib
import re
import types

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
RECORDS = []
REGISTRIES = []
JOB = 'probe'

def bind_text(value):
    if not isinstance(value,str): return value
    parts=value.split('/')
    for old in ('engine_v44_keep','engine_v45_verify','engine_v46_ui','engine_v47_fix','engine_v48_own'):
        if old in parts:
            at=parts.index(old)
            return str((ROOT/'firmware/engine_v49_knobs').joinpath(*parts[at+1:]))
    for old in ('package_v36_g122','package_v36_g123','package_v36_g124','package_v36_g126','package_v36_g127'):
        if old in parts:
            at=parts.index(old)
            return str((ROOT/'firmware/package_v36_g129').joinpath(*parts[at+1:]))
    return value

def named_generation(instructions,index):
    previous=instructions[max(0,index-18):index]
    following=instructions[index+1:index+3]
    if following and following[0].opname.startswith('STORE_'):
        return str(following[0].argval).lower() in ('generation','target_generation','gen','expected_generation')
    if not previous:return False
    last=previous[-1]
    if following and following[0].opname in ('COMPARE_OP','CONTAINS_OP'):
        if last.opname=='BINARY_SUBSCR' and len(previous)>1 and previous[-2].opname=='LOAD_CONST' and previous[-2].argval=='generation':return True
        if last.opname in ('LOAD_ATTR','LOAD_GLOBAL','LOAD_FAST','LOAD_NAME'):
            return str(last.argval).lower() in ('generation','expected_generation')
        if last.opname.startswith('POP_JUMP'):
            names=[v for v in previous if v.opname in ('LOAD_ATTR','LOAD_FAST','LOAD_NAME','LOAD_GLOBAL')]
            return bool(names) and str(names[-1].argval).lower() in ('generation','expected_generation')
    if last.opname=='LOAD_CONST' and last.argval=='generation':return True
    current=[]
    for item in reversed(previous):
        if item.opname.startswith('CALL_'):break
        current.append(item)
    parser_field=any(v.opname=='LOAD_CONST' and v.argval=='--generation' for v in current)
    setup_call=last.opname in ('LOAD_GLOBAL','LOAD_NAME','LOAD_METHOD') and last.argval=='setup'
    return parser_field or setup_call

def dictionary_generation(instructions):
    offsets=set()
    for index,item in enumerate(instructions):
        if item.opname!='BUILD_CONST_KEY_MAP' or index<1:continue
        keys=instructions[index-1]
        if keys.opname!='LOAD_CONST' or not isinstance(keys.argval,tuple) or 'generation' not in keys.argval:continue
        cursor=index-2;values=[];valid=True
        for _ in keys.argval:
            end=cursor;depth=1
            while cursor>=0 and depth>0:
                operation=instructions[cursor]
                if 'JUMP' in operation.opname:
                    valid=False;break
                depth-=dis.stack_effect(operation.opcode,operation.arg) if operation.arg is not None else dis.stack_effect(operation.opcode)
                cursor-=1
            if not valid or depth!=0:valid=False;break
            values.append((cursor+1,end))
        if not valid:continue
        first,last=list(reversed(values))[keys.argval.index('generation')]
        if first==last and instructions[first].opname=='LOAD_CONST':offsets.add(instructions[first].offset)
    return offsets

def bind(code,source_generation=None,target_generation=129):
    if source_generation is None:
        match=re.search(r'/review_g(\d+)/',code.co_filename)
        source_generation=int(match.group(1)) if match else 126
    versions=(source_generation,)
    constants=[bind(item,source_generation,target_generation) if isinstance(item,types.CodeType)
               else bind_text(item) for item in code.co_consts]
    instructions=list(dis.get_instructions(code)); raw=bytearray(code.co_code)
    dictionary_fields=dictionary_generation(instructions)
    for index,item in enumerate(instructions):
        if item.opname!='LOAD_CONST':continue
        old=item.argval
        is_number=type(old) is int and old in versions
        is_choices=isinstance(old,(tuple,frozenset)) and any(type(v) is int and v in versions for v in old)
        if not (is_number or is_choices):continue
        setup_choices=False
        prior=instructions[max(0,index-35):index]
        setup_number=(code.co_name=='setup' and is_number and
                      any(v.opname=='LOAD_GLOBAL' and v.argval=='DAT' for v in prior) and
                      any(v.opname=='LOAD_CONST' and v.argval==28 for v in prior) and
                      any(v.opname=='LOAD_CONST' and v.argval==32 for v in prior))
        if not (named_generation(instructions,index) or setup_choices or setup_number or item.offset in dictionary_fields):continue
        replacement=target_generation if is_number else type(old)(target_generation if type(v) is int and v in versions else v for v in old)
        new=next((i for i,value in enumerate(constants) if type(value) is type(replacement) and value==replacement),None)
        if new is None:new=len(constants);constants.append(replacement)
        if new>255:raise RuntimeError('named generation constant index exceeds one byte')
        if item.offset>=2 and raw[item.offset-2]==dis.opmap['EXTENDED_ARG']:
            raw[item.offset-1]=0
        raw[item.offset+1]=new
        RECORDS.append({'file':str(Path(code.co_filename).relative_to(ROOT)) if Path(code.co_filename).is_relative_to(ROOT) else Path(code.co_filename).name,'function':code.co_name,
                        'field':'generation','before':sorted(old) if isinstance(old,frozenset) else old,
                        'after':sorted(replacement) if isinstance(replacement,frozenset) else replacement})
    return code.replace(co_consts=tuple(constants),co_code=bytes(raw))

def self_check():
    source="generation=126\ndef chars(c):\n return 32<=c<=126\ndef field(v):\n return v['generation']==126\ndef combined(c):\n generation=126\n return generation,32<=c<=126\ndef metadata():\n return {'upper':126,'generation':126,'count':11}\n"
    env={};exec(bind(compile(source,'version_field_check','exec')),env)
    assert env['generation']==129 and env['field']({'generation':129})
    assert env['chars'](126) and not env['chars'](127)
    assert env['combined'](126)==(129,True) and env['combined'](127)==(129,False)
    assert env['metadata']()=={'upper':126,'generation':129,'count':11}
    return {'generation_field':129,'ascii_upper':126,'ascii_127_rejected':True}

def adjust(module):
    if Path(getattr(module,'__file__','')).name=='algorithm_check.py' and hasattr(module,'Algorithm'):
        import sys
        if str(WORK) not in sys.path:sys.path.insert(0,str(WORK))
        from r2_oracle import reference_class
        module.Algorithm=reference_class(module.OUT)
    if Path(getattr(module,'__file__','')).name=='ui_test_support.py':
        import sys
        if str(WORK) not in sys.path:sys.path.insert(0,str(WORK))
        from ui_adapter import install
        install(module)
    if module.__name__!='support':return
    if isinstance(getattr(module,'DAT',None),Path):
        raw=module.DAT.read_bytes()
        assert hashlib.sha256(raw).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
        assert int.from_bytes(raw[28:32],'big')==129 and len(raw)==89308
        if hasattr(module,'PIN'):module.PIN=hashlib.sha256(raw).hexdigest()
        REGISTRIES.append({'name':'candidate_identity','pin_match_count':int(hashlib.sha256(raw).hexdigest()==getattr(module,'PIN',None)),
                           'generation_count':int.from_bytes(raw[28:32],'big'),'byte_count':len(raw)})
    for name,value in list(vars(module).items()):
        if isinstance(value,Path):REGISTRIES.append({'name':name,'path_exists':int(value.exists())})

def setup_function(function):
    if getattr(function,'__code__',None) and function.__code__.co_name=='setup':
        function.__code__=bind(function.__code__)
        REGISTRIES.append({'name':'setup_version_constant','generation_count':sum(type(v) is int and v==129 for v in function.__code__.co_consts)})
