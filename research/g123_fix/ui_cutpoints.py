"""Schedule a real other_menu constructor immediately at the two late UI boundaries."""
from pathlib import Path
import copy
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_native as n
from ui_trace_scope import touches_ui,scope_records
from common import OUT,save,sha

def run(point,r,unit='50mm'):
    n.configure(unit,'ui-cutpoint-'+point);ux,m,fr,pe,v=n.ux,n.m,n.fr,n.pe,n.v
    h,p,w=m.boot(unit);m.published(h,p,w);ins=ux.instrument(h,p)
    h.b.map(0x206a0000,bytes(0x10000));state={'fired':False};writes=[]
    # Keep the verified CRC accelerator; this case checks writes and owner
    # handoff, not instruction cost.
    def watch(ev):
        if state['fired'] and touches_ui(ev):
            writes.append(dict(address=hex(ev.address),data=ev.data.hex(),pc=hex(ev.pc)))
    h.b.add_write_trace(0,2**32,watch)
    def simulate(b):
        if state['fired']:return False
        if point=='redraw' and (b.core.r[0]!=10 or b.core.r[1]!=3):return False
        shadow_b=v.PythonBackend();shadow_b.regions=h.b.regions;shadow_b.mmio=h.b.mmio;shadow_b.traces=h.b.traces
        shadow_b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()};shadow_b.core.r=list(b.core.r)
        shadow_b.core.psw=b.core.psw;shadow_b.core.cr=dict(b.core.cr);shadow_b.core.bpsw=b.core.bpsw;shadow_b.core.bbpsw=b.core.bbpsw;shadow_b.core.acc=b.core.acc
        shadow_b.set_reg('r15',0x206afff0);shadow=copy.copy(h);shadow.b=shadow_b
        # Mark only after construction, so its legitimate native writes are
        # distinct from any late engine write under test.
        shadow.run_slice(0x202ba380,0x202ba3c8);shadow.leave_other_list()
        state.update(fired=True,after_native=ux.snap(h,p),inflight=h.u(pe.ROOT_ADDR+6,1))
        return False
    h.b.add_breakpoint(p.symbol_pc('rv_call' if point=='redraw' else 'cursor_cache'),simulate)
    r['outer']=ux.need(fr.move_key(h,0x20));r['after']=ux.snap(h,p);r['actual']=ux.matches(h,p,4)
    assert state['fired'] and state['inflight']==1
    assert not writes,writes
    assert r['after']['W']==r['after']['preview_calls']==0
    assert r['after']['cursor']==r['after']['dot_row']==7
    assert r['after']['native_activity']==7 and r['after']['native_overlay']==21
    assert r['after']['root']['state']==3 and not r['after']['list']['uncertain']
    if point=='redraw':assert r['after']['rpc']==0
    r.update(status='PASS',point=point,schedule=state,writes_after_switch=writes,ui_trace_scope=scope_records(),
        dat_sha256=sha(m.DAT.read_bytes()),file_mutations=m.no_writes(p),native_ui_hand_seeded=False)
    print('PASS late UI boundary',point,'RPC',r['after']['rpc'],'W=0 native_preview=0 late_UI_writes=0; pure04',flush=True)

if __name__=='__main__':
    point=sys.argv[1];unit=sys.argv[2] if len(sys.argv)>2 else '50mm';r={'unit':unit}
    try:run(point,r,unit)
    except Exception:r.update(status='FAIL',error=traceback.format_exc());raise
    finally:save('local/native/ui-cutpoint-'+point+'-'+unit+'.json',r)
