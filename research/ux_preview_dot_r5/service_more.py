"""Additional final-machine pairs for RPC results and valid settings plans."""
from pathlib import Path
import itertools
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import service_targets as s
from common import save,sha

p=s.d.Pair();s.setup(p);rows=[];seen={119:set(),120:set()}
def run(sid,op,label,modify):
    args=s.base(p,sid,op,len(rows));modify()
    s.execute(p,args,label,len(rows),rows,seen)

for op,value,phase,ready,limit in itertools.product(range(1,6),(-1,0,1,0x1234,65536),range(4),(0,1),(8,9)):
    def modify(op=op,value=value,phase=phase,ready=ready,limit=limit):
        p.mode['rpc_result']=value
        p.mode['returns'].update(rv_native_rpc_ready=[ready],rv_native_rpc_limit=[limit])
        for r in p.rs:r.w32(s.S+388,phase)
    run(4,op,dict(service=4,op=op,result=value,phase=phase,ready=ready,limit=limit),modify)

for count,offset,value,mode in itertools.product((0,1,3,16,17),(0x36e,0x6dd,0x6de,0x36f,0x645,0x641,4095),(0,1,2,9,17,18),(1,3,4,6)):
    def modify(count=count,offset=offset,value=value,mode=mode):
        for r in p.rs:
            r.w32(s.B+12,count)
            r.write(s.D+0x14000+0x36e,bytes([mode]))
            r.write(s.B+16,struct.pack('>HBB',offset,value,0))
    run(6,2,dict(service=6,count=count,offset=offset,value=value,mode=mode),modify)

save('service-more.json',dict(status='PASS',cases=rows,edges={g:sorted(e) for g,e in seen.items()},
    artifacts={r.g:dict(elf=sha(r.e.raw),dat=sha(r.original)) for r in p.rs},
    scope='Named common boundary contracts. Dispatcher bodies execute final M32R instructions. No UI state or device effect is claimed.'))
print('PASS additional service machine comparisons',len(rows),'pairs',flush=True)
