"""Raw half-shutter after full native ADJ item selection and deferred H01."""
from pathlib import Path
import json
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

def main():
    ux,m,fr,pe,v=setup(tag='official-half')
    sequence=load(MATERIALS/'native_sequence.py','review_official_sequence')
    h,p,w=m.boot('50mm')
    sequence.device_edges(h,p)
    report=dict(input=sequence.prepare_input(h))
    h.parent();m.published(h,p,w)
    h.select_item_8()
    report['native_entry']=sequence.open_image_from_adj(h,p,fr)
    ux.need(fr.move_key(h,0x20))
    ux.matches(h,p,5)
    report['exit']=sequence.key(h,fr,0x17)
    assert h.u(0x2037f3bc)==0
    p.rpc.overlay.clear();p.rpc.t=2
    original=p.rpc.call
    def busy(cmd,value):
        p.rpc.log.append(dict(cmd=cmd,value=value,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
        return -1
    p.rpc.call=busy
    h.parent()
    opened,_,error=fr.publish(h,p,w)
    ux.need(opened);assert error is None,error
    report['pending']=ux.snap(h,p)
    assert report['pending']['rows']==8 and report['pending']['cursor']==report['pending']['dot_row']==5
    # The unit is available again before the half-press, so communication
    # readiness cannot explain skipping the retry.
    p.rpc.call=original
    events=[]
    for name in ('ig_event','ig_apply','ig_panel_open','ig_stop'):
        def entered(b,name=name):events.append(name);return False
        h.b.add_breakpoint(p.symbol_pc(name),entered)
    native=[]
    for pc in (0x2029fdc4,0x202bd724,0x202bd890,0x202bea54):
        def entered(b,pc=pc):native.append(hex(pc));return False
        h.b.add_breakpoint(pc,entered)
    at=len(p.rpc.log)
    hook_mark=w.mark()
    report['half']=sequence.key(h,fr,0xd)
    report['resident_hooks']=w.since(hook_mark)
    report['after_half']=ux.snap(h,p)
    report['entry_calls']=events
    report['native_handlers']=native
    report['half_RPC']=len(p.rpc.log)-at
    report['stock']=ux.matches(h,p,4)
    try:
        ux.matches(h,p,5)
    except AssertionError:
        report['recipe5_matches']=False
    else:
        report['recipe5_matches']=True
    assert report['half']['logical']==0x29
    assert report['half_RPC']==0 and not report['recipe5_matches'] and not events
    assert report['after_half']['native_overlay']==0
    assert native, 'Raw half-shutter must reach a native Image event handler.'
    report['file_mutations']=m.no_writes(p)
    report['native_UI']=ui_audit(h)
    report['dat_sha256']=sha(p.dat)
    report['status']='COUNTEREXAMPLE_REPRODUCED'
    save('local/official-half-with-hooks.json' if '--hook-trace' in sys.argv else 'local/official-half.json',report)
    print(json.dumps(dict(status=report['status'],half_RPC=report['half_RPC'],native_handlers=native)))

if __name__=='__main__':
    main()
