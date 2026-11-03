"""Check the next native menu open on the retained live model."""
import hashlib,json
from pathlib import Path

def run(context,tail,out,sessions):
    ux,m,fr,pe,v=context
    h,p,w=sessions[-1]
    unit=tail[tail.index('--unit')+1]
    before=ux.snap(h,p)
    assert before['native_activity']==7 and before['native_overlay']==21
    assert before['mode']==5
    address=h.u(0x200c0dac)
    assert address==h.settings
    core=p.symbol_pc('g')
    pending_before=h.u(core+2540,1)
    assert pending_before==1
    result=m.reopen(h,p,w)
    after=ux.snap(h,p)
    values={hex(offset):h.u(address+offset,1) for offset in (0x36e,0x6dd,0x6de)}
    pending_after=h.u(core+2540,1)
    assert values=={'0x36e':1,'0x6dd':9,'0x6de':9},values
    assert after['rows']==8 and ux.matches(h,p,4)
    assert after['preview_calls']>before['preview_calls']
    assert pending_after==0
    record={'status':'PASS','generation':127,'unit':unit,
            'dat_sha256':hashlib.sha256(p.dat).hexdigest(),
            'pending_before':pending_before,'pending_after':pending_after,
            'settings_after':values,'before':before,'after':after}
    target=out/'evidence'/('ownership-reopen-127-'+unit+'.json')
    target.write_text(json.dumps(record,indent=2)+'\n')
    print('PASS next native open',unit,values)
