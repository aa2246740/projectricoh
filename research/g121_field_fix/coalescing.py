"""Compare 119/120 after genuine same-page native arrows run during RPC."""
from pathlib import Path
import argparse
import copy
import json
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from common import ROOT,OUT,save,sha

def run(gen,unit,at,r):
    ux,m,fr,pe,v=n.ux,n.m,n.fr,n.pe,n.v
    n.configure(unit,'coalescing-'+str(gen)+'-at'+str(at))
    if gen==119:
        dat=ROOT/'firmware/package_v36_g119/SD_ROOT/GXRCE.DAT'
        elf=ROOT/'firmware/engine_v40_ux/candidate/local/full-r13/engine.elf'
        m.DAT=pe.STAGED=dat;pe.STAGED_SHA=sha(dat.read_bytes());pe.ENGINE_ELF=elf
    h,p,w=m.boot(unit);ins=ux.instrument(h,p);m.published(h,p,w);ux.arm_entries(h,p,ins)
    h.b.map(0x206a0000,bytes(0x10000));original=p.rpc.call
    state=dict(fired=False,seen=0);transactions=[]
    def apply(b):
        transactions.append(dict(slot=h.u(b.core.r[0]+1,1),recovery=b.core.r[2],rpc_index=len(p.rpc.log),W=0))
        return False
    h.b.add_breakpoint(p.symbol_pc('apply_impl'),apply)
    def call(cmd,value):
        state['seen']+=1
        if state['seen']==at:
            state['fired']=True;state['W_before_switch']=sum(x['cmd']==22 for x in p.rpc.log)
            b=v.PythonBackend();b.regions=h.b.regions;b.mmio=h.b.mmio;b.traces=h.b.traces
            b.breakpoints={k:list(v) for k,v in h.b.breakpoints.items()};b.core.r=list(h.b.core.r)
            b.core.psw=h.b.core.psw;b.core.cr=dict(h.b.core.cr);b.core.bpsw=h.b.core.bpsw;b.core.bbpsw=h.b.core.bbpsw;b.core.acc=h.b.core.acc
            b.set_reg('r15',0x206afff0);shadow=copy.copy(h);shadow.b=b
            state['inflight']=h.u(pe.ROOT_ADDR+6,1);state['native']=[]
            for _ in range(2):state['native'].append(ux.need(fr.move_key(shadow,0x20)))
            state['last_row']=h.u(0x2022f726,1)
        if cmd==22:transactions[-1]['W']+=1
        return original(cmd,value)
    p.rpc.call=call
    step=ux.measure_move(h,p,0x20,ins);p.rpc.call=original
    assert state['fired'] and state['inflight']==1 and state['last_row']==7
    assert step['after']['cursor']==7 and step['final_draw_marker']['row']==7
    actual=ux.matches(h,p,7)
    assert [x['slot'] for x in transactions]==[5,7],transactions
    if gen==121 and at==1:
        assert transactions[0]['W']==0 and step['refreshes']==1
    else:assert transactions[0]['W']>0 and step['refreshes']==2
    r.update(status='PASS',generation=gen,unit=unit,at=at,dat_sha256=sha(m.DAT.read_bytes()),
        schedule=state,step=step,transactions=transactions,actual=actual,file_mutations=m.no_writes(p),
        scope='Two arrows execute native handlers in an independent task context sharing RAM; no manual UI/resident state writes. Does not inspect unprocessed OS message queues.')
    print('PASS coalescing',gen,unit,'at',at,'RPC',step['rpc_calls'],'unit B',step['unit_write_bytes'],'previews',step['refreshes'],'transactions',transactions,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('generation',type=int,choices=(119,120,121));p.add_argument('unit',choices=('50mm','28mm','mount'));p.add_argument('--at',type=int,default=1);a=p.parse_args()
    r={}
    try:run(a.generation,a.unit,a.at,r)
    except Exception:r.update(status='FAIL',error=traceback.format_exc());raise
    finally:save('native/coalescing-'+str(a.generation)+'-'+a.unit+'-at'+str(a.at)+'.json',r)

if __name__=='__main__':main()
