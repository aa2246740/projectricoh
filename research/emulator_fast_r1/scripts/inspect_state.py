"""Inspect transport sizes without executing firmware."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable
enable()
import bootstrap
from collections import Counter,deque
ctx=bootstrap.construct('fast','boot','inspect-state-2')
from native_machine import NativeMachine
d=NativeMachine(ctx.machine.cpu);assert d.supported()
payload=d.collect(resources=True)
records=[];counts=Counter();largest=[]
def walk(v,path):
    counts[type(v).__name__]+=1
    if isinstance(v,(bytes,bytearray,str)):largest.append((len(v),path))
    if isinstance(v,int) and v.bit_length()>256:records.append((path,type(v).__name__,v.bit_length()))
    elif isinstance(v,dict):
        for k,item in v.items():walk(k,path+'/key');walk(item,path+'/'+str(k))
    elif isinstance(v,(list,tuple,set,frozenset,deque)):
        for i,item in enumerate(v):walk(item,path+'/'+str(i))
    elif type(v).__name__=='UnitLink':walk(v.__dict__,path+'/UnitLink')
walk(payload,'root')
print(json.dumps(dict(records=records,counts=counts,largest=sorted(largest,reverse=True)[:10])),flush=True)
import cProfile
import wire
profile=cProfile.Profile();profile.enable()
began=time.perf_counter();raw=wire.encode(payload,d.opaque);print('encode',len(raw),time.perf_counter()-began,flush=True)
profile.disable();profile.dump_stats(str(bootstrap.HERE/'runs/inspect-wire.prof'))
ctx.machine.close()
