"""Check refusal against actual unit rows when the first-open baseline is unverified."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import independent_checks as I
import g150_checks as F
import review_checks as C
import decode as D


def set_unit_rows(cam,entry):
    table=C.mapping(cam)
    for row in range(9):
        address=int.from_bytes(table[32+12*row:36+12*row],'big')
        size=int.from_bytes(table[36+12*row:38+12*row],'big')
        offset=int.from_bytes(table[38+12*row:40+12*row],'big')
        for k,value in enumerate(entry[offset:offset+size]):
            at=address+k;word=at&~1;old=cam.p.rpc.half(word)
            assert old is not None
            cam.p.rpc.overlay[word]=(old&0xff00)|value if at&1 else (value<<8)|(old&0xff)
    cam.p.rpc.t=int.from_bytes(entry[445:447],'big')


def check(unit,kind):
    cam=I.H.Camera(unit)
    raw=I.H.DAT_BYTES[cam.dat_path];module=D.modules(raw)[I.H.UNITS[unit]]
    prior_entry=module['entries'][module['refs'][1]]
    target_entry=module['entries'][module['refs'][4]]
    stock_entry=module['entries'][module['refs'][3]]
    set_unit_rows(cam,prior_entry)
    cam.put_s(0x36e,b'\x04')
    before_open=I.snapshot(cam)
    cam.open_menu();initial=cam.check_frame()
    before=I.snapshot(cam)
    assert (before['rows'],before['T'])==I.expected_rows(cam,prior_entry)
    assert before['rows']!=I.expected_rows(cam,stock_entry)[0]
    assert before['rows']==before_open['rows'] and before['T']==before_open['T']
    assert before['S']==before_open['S'] and before['W']==before_open['W']==0
    assert not any(t.startswith('>') for t in initial['labels'])
    cam.h.b.core.psw |= 0x40
    calls=[];taken=[];stores=F.s_stores(cam)
    def call(b):
        key=tuple(b.core.r[:2])
        if key[0]==6 and key[1] in (2,5,6):
            if key==(6,2) and kind=='late' and not taken:
                assert b.core.psw & 0x40, 'owner scheduling point must have IRQ enabled'
                C.model_lock(cam,0);taken.append(True)
            row=dict(op=key[1],lock=cam.lock(),irq_enabled=bool(b.core.psw&0x40));calls.append(row)
            def returned(current):
                n=current.core.r[0];row['returned']=n-2**32 if n>=2**31 else n
            I.callback_return(cam,b,returned)
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    if kind=='held':C.model_lock(cam,0)
    cam.press('DOWN');after=I.snapshot(cam);frame=cam.check_frame()
    if kind=='held':
        assert cam.unit_rows()==(before['rows'],before['T'])
        assert after['S']==before['S'] and after['W']==before['W'] and not stores
        status='PASS_M32R'
    elif kind=='idle':
        assert cam.unit_rows()==I.expected_rows(cam,target_entry)
        assert cam.s_bytes(0x36e,1)==b'\x01' and cam.record()==I.record(cam,5,F.ZERO)
        assert frame['labels'][4]=='>5 F-CC' and not frame['failed']
        status='PASS_M32R'
    else:
        assert taken and cam.unit_rows()==I.expected_rows(cam,stock_entry)
        assert cam.unit_rows()!=(before['rows'],before['T']) and cam.unit_rows()!=I.expected_rows(cam,target_entry)
        assert after['S']==before['S'] and not stores and after['W']-before['W']==506
        assert [(c['op'],c['returned']) for c in calls]==[(6,0),(2,-2)],calls
        assert cam.record()==bytes(40) and not frame['failed'] and not any('Unsaved' in t for t in frame['labels'])
        status='OBSERVED_P1'
    F.do_exit(cam,'ok');closed=cam.state();cam.open_menu();reopened=cam.check_frame()
    if kind=='late':
        assert closed['rows']==7 and cam.unit_rows()==I.expected_rows(cam,stock_entry)
        assert cam.s_bytes(0,4096)==before['S'] and not reopened['failed']
    return cam,dict(kind=kind,model_input='valid recipe 02 rows and T; S mode 4 as in the original busy case; no UI or engine state writes',
                    initial=initial,before=I.serial_snapshot(before),after=I.serial_snapshot(after),
                    frame=frame,closed=closed,reopened=reopened,calls=calls,S_stores=stores,
                    prior_entry_sha256=I.sha(prior_entry),target_entry_sha256=I.sha(target_entry),
                    stock_entry_sha256=I.sha(stock_entry),observation_status=status,
                    finding='late S busy replaces actual prior 02 rows with stock without ERR' if kind=='late' else None)


if __name__=='__main__':
    I.CASES.clear();I.CASES.update({name:lambda unit,kind=kind:check(unit,kind) for name,kind in
                                  (('unverified-held','held'),('unverified-idle','idle'),('unverified-late','late'))})
    I.main()
