"""Check a full-vector reopen and all adapter views in the same session."""
from pathlib import Path
import hashlib
import json
import runpy

ROOT=Path(__file__).resolve().parents[2]

def restore(context,arguments,out,sessions):
    ux,model,fr,pe,v=context
    h,p,w=sessions[-1]
    unit=arguments[arguments.index('--unit')+1]
    layout=json.loads((out/'local/layout/layout.json').read_text())
    pending=p.symbol_pc('g')+layout['recheck']+1
    before=ux.snap(h,p)
    assert before['native_activity']==7 and before['native_overlay']==21 and before['mode']==5
    assert h.u(pending,1)==1
    model.reopen(h,p,w)
    after=ux.snap(h,p)
    address=h.u(0x200c0dac)
    assert {hex(offset):h.u(address+offset,1) for offset in (0x36e,0x6dd,0x6de)}=={'0x36e':1,'0x6dd':9,'0x6de':9}
    assert after['rows']==8 and ux.matches(h,p,4)
    assert after['preview_calls']>before['preview_calls'] and h.u(pending,1)==0
    (out/f'reopen-{unit}.json').write_text(json.dumps({'status':'PASS','unit':unit,
        'dat_sha256':hashlib.sha256(p.dat).hexdigest(),'pending_offset':layout['recheck']+1},indent=2)+'\n')
    return h,p,w

def run(context,arguments,out,sessions):
    restore(context,arguments,out,sessions)
    capture=runpy.run_path(str(ROOT/'research/g129_knobs/session_check.py'))
    capture['capture'](context,arguments,out,sessions)
    product=runpy.run_path(str(ROOT/'research/g129_knobs/product_checks.py'))
    product['run'](context,arguments,out,sessions)
