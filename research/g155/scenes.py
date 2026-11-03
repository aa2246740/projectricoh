"""按原函数复用已用过的单元状态和锁时序场景。"""
from pathlib import Path
import ast
import hashlib
import struct
import types
from native_support import H,load

ROOT=H.ROOT
SOURCES={}


def existing(path,name,namespace,owner=None):
    text=Path(path).read_text();tree=ast.parse(text)
    nodes=tree.body if owner is None else next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner).body
    node=next(n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    scope=dict(namespace);exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    SOURCES[str(Path(path).relative_to(ROOT))+':'+name]=hashlib.sha256(ast.get_source_segment(text,node).encode()).hexdigest()
    return scope[name]


C=types.SimpleNamespace()
review=ROOT/'research/v39_g153/legacy/review_checks.py'
C.mapping=existing(review,'mapping',dict(H=H))
C.model_lock=existing(review,'model_lock',dict(H=H))
P=types.SimpleNamespace()
P.set_unit_rows=existing(ROOT/'research/v39_g153/legacy/previous_state_checks.py','set_unit_rows',dict(C=C))
LOCK=load(ROOT/'research/v39_g153/lock_checks.py','g154_shared_lock')
callback_return=LOCK.callback_return
entry_method=existing(ROOT/'research/cpu_speed_probe/accept_cpuprobe.py','entry',dict(R=H.R,struct=struct),owner='Session')


def entry(cam,index,args=None):
    context=types.SimpleNamespace(h=cam.h,p=cam.p,pe=cam.m.pe)
    return entry_method(context,index,args)
