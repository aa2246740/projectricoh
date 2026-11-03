"""Readiness, changed second reads, retained E, and public lifecycle entries."""
from pathlib import Path
import argparse
import json
import os
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
from trace import *
from functional import assert_page


def run(unit,kind):
    h,p,w,arm=setup(unit,ready=0 if kind=='cold_ready' else 1)
    audit=Audit(h,p,arm)
    record=dict(unit=unit,kind=kind)
    if kind=='cold_ready':
        h.parent();record['deferred']=need(fr.native(h,0x20287080,steps=30000000))
        assert not p.image_base and h.u(0x2022f5ac,1)==7 and h.u(pe.ROOT_ADDR+5,1)==0
        record['deferred_entries']=list(audit.entries)
        assert not audit.entries
        need(fr.native(h,0x200935b4,(1,)))
        record['opened']=open_menu(h,p);assert_page(h,p,'A',1)
    elif kind=='changed':
        injected=[False]
        def changed():
            if injected[0]:return
            injected[0]=True
            audit.external=True
            try:need(fr.native(shadow(h),0x200935b4,(0,)))
            finally:audit.external=False
        audit.capture_pass_hook=changed
        record['opened']=open_menu(h,p)
        assert injected[0] and private(h,p,'changed',1)==1
        assert_page(h,p,'A',1)
        assert text_rows(h,p)[0].endswith('C')
        for _ in range(4):action(h,p,'disp')
        assert_page(h,p,'F',1)
        assert text_rows(h,p)[6]=='00000000' and text_rows(h,p)[7]=='00000001'
        cap=audit.captures[0]
        assert [e['field'] for e in cap]==LAYOUT['field_order']*2
        assert cap[48]['field']=='rpc_ready' and cap[48]['value']==1
        assert cap[98]['field']=='rpc_ready' and cap[98]['value']==0
        record['after']=snapshot(h,p)
    elif kind=='warm_ready':
        open_menu(h,p);action(h,p,'ok')
        need(fr.native(h,0x200935b4,(0,)))
        record['opened']=open_menu(h,p)
        for _ in range(4):action(h,p,'disp')
        assert_page(h,p,'F',2)
        assert text_rows(h,p)[6]=='00000000'
        record['after']=snapshot(h,p)
    elif kind=='error':
        fired=audit.arm_error_page(arm)
        record['opened']=open_menu(h,p)
        assert fired[0] and private(h,p,'error',1)==1 and h.u(0x2022f5ac,1)==8
        record['disp']=action(h,p,'disp')
        assert text_rows(h,p)==['E0001 U','NO DATA','NOT ZERO','RAW ONLY','NO RPC','NO FILE','CLOSE','REOPEN']
        record['error_page']=snapshot(h,p)
        for name in ('up','down','disp'):
            action(h,p,name)
            assert h.u(0x2022f5ac,1)==8 and text_rows(h,p)[0]=='E0001 U'
        action(h,p,'ok');assert h.u(0x2037f3bc)==0
        record['reopen']=open_menu(h,p);assert_page(h,p,'A',2)
    elif kind in ('panel_event','panel_abort','stop'):
        record['opened']=open_menu(h,p)
        p.accelerate_crc=lambda _:None
        slot=dict(panel_event=4,panel_abort=5,stop=7)[kind]
        result=p.engine(slot,[])
        assert result.get('ok') and result['signed'] in (1,2),result
        record['entry_result']=result
        assert h.u(0x2022f5ac,1)==8
    elif kind=='raw_half':
        sequence=load(ROOT/'research/g123_fix/native_sequence.py','diag_raw_sequence')
        sequence.device_edges(h,p)
        audit.bp(0x2009005c,lambda b:audit.native_call(b,'ipc',b.core.r[4]))
        record['task_setup']=sequence.prepare_input(h)
        record['native_selection']=need(fr.native(h,0x202c1fd4))
        assert h.u(h.settings+0x39f,1)==2
        open_menu(h,p)
        record['exit']=sequence.key(h,fr,0x17)
        assert h.u(0x2037f3bc)==0
        record['native_entry']=open_menu(h,p)
        h.select_item_8()
        handlers=[]
        for pc in (0x2029fdc4,0x202bd724,0x202bd890,0x202bea54):
            h.b.add_breakpoint(pc,lambda b,pc=pc:handlers.append(hex(pc)) or False)
        record['half']=sequence.key(h,fr,0xd)
        record['native_handlers']=handlers
        assert record['half']['logical']==0x29
        assert '0x202bd724' in handlers,handlers
        assert h.u(0x2037f3bc)==0
        record['after']=snapshot(h,p)
    else:raise ValueError(kind)
    record['audit']=audit.result()
    record['status']='PASS'
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    parser.add_argument('--kinds',nargs='+',default=['cold_ready','changed','warm_ready','error','panel_event','panel_abort','stop','raw_half'])
    args=parser.parse_args();results=[]
    for kind in args.kinds:
        record=dict(unit=args.unit,kind=kind)
        try:record.update(run(args.unit,kind))
        except BaseException:record.update(status='FAIL',error=traceback.format_exc())
        save(OUT/'local/variants'/f'{args.unit}-{kind}.json',record)
        print(args.unit,kind,record['status'],record.get('error','')[-800:],flush=True)
        results.append(dict(kind=kind,status=record['status']))
    save(OUT/'evidence'/f'variants-{args.unit}.json',dict(dat_sha256=sha(DAT),results=results,
        status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL'))
    assert all(x['status']=='PASS' for x in results),results


if __name__=='__main__':main()
