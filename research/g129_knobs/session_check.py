"""Run the retained reopen check and export the real target session state."""
from pathlib import Path
import json
import runpy
import sys
import hashlib
import importlib.machinery
import types
ROOT=Path(__file__).resolve().parents[2]

def capture(context,arguments,out,sessions):
    unit=arguments[arguments.index('--unit')+1] if '--unit' in arguments else 'unit'
    objects=[]
    for session in sessions:
        objects.extend(session if isinstance(session,tuple) else (session,))
    description=[]
    for obj in objects:
        fields={}
        for name,value in vars(obj).items() if hasattr(obj,'__dict__') else ():
            if isinstance(value,(int,str,bool,type(None))):fields[name]=value
            elif isinstance(value,(bytes,bytearray)):fields[name]={'bytes':len(value)}
            else:fields[name]=type(value).__name__
        description.append({'class':type(obj).__name__,'fields':fields})
    (out/f'target-session-{unit}.json').write_text(json.dumps(description,indent=2)+'\n')
    found=[]
    for obj in objects:
        candidates=[obj,getattr(obj,'b',None),getattr(getattr(obj,'h',None),'b',None)]
        for backend in candidates:
            if hasattr(backend,'regions') and hasattr(backend,'get_reg') and backend not in found:found.append(backend)
    for number,backend in enumerate(found):
        folder=out/f'target-state-{unit}-{number}';folder.mkdir(exist_ok=True)
        regions=[]
        for index,(base,data,writable) in enumerate(backend.regions):
            name=f'region-{index}.bin';(folder/name).write_bytes(bytes(data))
            regions.append({'base':base,'bytes':len(data),'writable':writable,'file':name})
        state={'regions':regions,'registers':{f'r{i}':backend.get_reg(f'r{i}') for i in range(16)}}
        (folder/'state.json').write_text(json.dumps(state,indent=2)+'\n')
        (folder/'stack-calls.json').write_text(json.dumps(getattr(backend,'g129_stack_calls',[]),indent=2)+'\n')
def run(context,arguments,out,sessions):
    capture(context,arguments,out,sessions)
    digest=hashlib.sha256((ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest()
    layout=json.loads((out/'local/layout/layout.json').read_text())
    pending_offset=layout['recheck']+1
    (out/'reopen-layout-binding.json').write_text(json.dumps({'settings_pending':{'before':2540,'after':pending_offset}},indent=2)+'\n')
    def bind(code):
        def value(item):
            if isinstance(item,types.CodeType):return bind(item)
            if type(item) is int and item==127:return 129
            if type(item) is int and item==2540:return pending_offset
            if isinstance(item,tuple):return tuple(value(x) for x in item)
            if isinstance(item,str):
                item=item.replace('engine_v48_own','engine_v49_knobs').replace('package_v36_g127','package_v36_g129')
                if item=='9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6':return digest
            return item
        return code.replace(co_consts=tuple(value(item) for item in code.co_consts))
    path=ROOT/'research/g127_fix/ownership_reopen.py'
    check={'__name__':'g129_reopen_check','__file__':str(path)}
    loader=importlib.machinery.SourceFileLoader('g129_reopen_check',str(path))
    exec(bind(loader.get_code('g129_reopen_check')),check)
    check['run'](context,arguments,out,sessions)
