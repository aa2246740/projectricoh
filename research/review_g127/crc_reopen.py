"""Keep native CRC active for the retained ownership and next-open check."""
from pathlib import Path
import hashlib
import json
import runpy

def run(context, tail, out, sessions):
    ux,m,fr,pe,v=context
    h,p,w=sessions[-1]
    address=p.symbol_pc('gxr2_crc_add')
    removed=len(h.b.breakpoints.pop(address,[]))
    p.crc_fast=True
    before=h.b.visits[address]
    calls=h.stub_hits.get('gxr2_crc_add',0)
    root=Path(__file__).resolve().parents[2]
    check=runpy.run_path(str(root/'research/g127_fix/ownership_reopen.py'),run_name='crc_check')
    check['run'](context,tail,out,sessions)
    value=dict(status='PASS',unit=tail[tail.index('--unit')+1],
               dat_sha256=hashlib.sha256(p.dat).hexdigest(),
               removed_host_callbacks=removed,callbacks_after=len(h.b.breakpoints.get(address,[])),
               native_entry_visits=h.b.visits[address]-before,
               host_calls=h.stub_hits.get('gxr2_crc_add',0)-calls,
               pending=h.u(p.symbol_pc('g')+2540,1),mode=h.u(h.settings+0x36e,1))
    assert value['callbacks_after']==0 and value['host_calls']==0 and value['native_entry_visits']>0
    (out/'evidence/crc-native-ownership.json').write_text(json.dumps(value,indent=2)+'\n')

