"""Targeted native boundary samples; never assign native UI fields."""
from pathlib import Path
import argparse
import copy
import json
import os
import struct
import sys
import traceback
HERE = Path(__file__).resolve().parent
# review_g126 supplies the support layer the g135 runner binds; run_cases only exists in review_g124
sys.path.insert(0, str(HERE.parent / 'review_g124'))
sys.path.insert(0, str(HERE.parent / 'review_g126'))
sys.path.insert(0, str(HERE))
from support import *
from run_cases import prepare

def shadow(h, v):
    h.b.map(0x206a0000, bytes(0x10000))
    b = v.PythonBackend()
    b.regions, b.mmio, b.traces = h.b.regions, h.b.mmio, h.b.traces
    b.breakpoints = {k:list(x) for k,x in h.b.breakpoints.items()}
    b.core.r, b.core.psw = list(h.b.core.r), h.b.core.psw
    b.core.cr = dict(h.b.core.cr)
    b.core.bpsw, b.core.bbpsw, b.core.acc = h.b.core.bpsw, h.b.core.bbpsw, h.b.core.acc
    b.set_reg('r15', 0x206afff0)
    other = copy.copy(h)
    other.b = b
    return other

def rpc_guard(p, m):
    _, mapping = m.unpack(p.dat, m.INDEX[p.unit], 5)
    rows = [struct.unpack_from('>IH', mapping, 32+12*i) for i in range(9)]
    tp, ti = struct.unpack_from('>HH', mapping, 28)
    pages = {a>>16 for a,n in rows} | {(a+n-1)>>16 for a,n in rows} | {tp}
    actual = p.rpc.call
    audit = dict(X=0,V=0,W=0,preserved_edges=0,violations=0)
    def checked(cmd, val):
        if cmd==23:
            assert val in pages, ('page', cmd, val)
            audit['X'] += 1
        elif cmd in (21,22):
            audit['V' if cmd==21 else 'W'] += 1
            if p.rpc.page==tp:
                if cmd==21:
                    assert val==ti
            else:
                at=(p.rpc.page<<16)|(val&~1) if cmd==21 else p.rpc.cursor
                spans=[(a,n) for a,n in rows if (a&~1)<=at and at+2<=((a+n+1)&~1)]
                assert spans, (cmd,hex(at))
                if cmd==22:
                    a,n=spans[0]
                    old=p.rpc.half(at)
                    if at<a:
                        assert old>>8==val>>8
                        audit['preserved_edges'] += 1
                    if at+2>a+n:
                        assert old&255==val&255
                        audit['preserved_edges'] += 1
        else:
            raise AssertionError(('command',cmd))
        return actual(cmd,val)
    p.rpc.call=checked
    return audit

def triage_ui(h, p, core, adapter):
    """Read the adapter UI state (adapter layout bytes) and core flags for triage."""
    n = p.symbol_pc('n'); g = p.symbol_pc('g')
    ui = n + adapter['ui']
    lv = [h.u(n + adapter['ui.levels'] + 2*i, 2) for i in range(10)]
    lv = [x - 65536 if x & 0x8000 else x for x in lv]
    text = [bytes(h.b.read(n + adapter['ui.text'] + 9*i, 9)).split(b'\0')[0].decode('latin1') for i in range(8)]
    out = {k: h.u(n + adapter[k], 1) for k in ('ui.screen','ui.cur','ui.top','ui.physical','ui.count','ui.slot','ui.param','ui.group','ui.armed','ui.applied_user',
                                                'failed','watch_view','view_lost','comm_failed','retry','ui_failed')}
    out['levels'] = lv
    out['text'] = text
    out['core'] = {k: h.u(g + core[k], 1) for k in ('ready','bound','busy','committed','uncertain','stage','confirmed_valid','previewing','write_started','recheck')}
    return out

def triage_expected(m, p, slot, levels):
    """Entry bytes from the frozen r2 C reference for (unit, slot, levels)."""
    import r2_oracle
    Ref = r2_oracle.reference_class(OUT)
    ref = Ref(); ref.unit = p.unit; ref.slot = slot
    entry, mapping = m.unpack(p.dat, m.INDEX[p.unit], slot)
    stock, _ = m.unpack(p.dat, m.INDEX[p.unit], 4)
    return ref.compute(bytes(entry), bytes(stock), list(levels)), mapping, entry

def triage_compare(m, h, p, slot, levels):
    out, mapping, entry = triage_expected(m, p, slot, levels)
    rows = []
    for i in range(9):
        r = mapping[32+12*i:44+12*i]
        address, nbytes, off = m.u32(r, 0), m.u16(r, 4), m.u16(r, 6)
        expected = bytes(out[off:off+nbytes])
        actual = bytes((p.rpc.half(a & ~1) >> (0 if a & 1 else 8)) & 255 for a in range(address, address+nbytes))
        rows.append(dict(row=i, equal=actual == expected, actual=m.sha(actual), expected=m.sha(expected)))
    return dict(slot=slot, levels=list(levels), rows_equal=all(x['equal'] for x in rows), rows=rows,
                T_actual=p.rpc.t, T_expected=m.u16(out, 445))

def run(name, fixture, r):
    ux,m,fr,pe,v,h,p,w,prepared=fixture
    r.update(prepared)
    scope=load(MATERIALS/'ui_trace_scope.py','review_ui_scope')
    core=json.loads((OUT/'local/layout/layout.json').read_text())
    adapter=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
    r['triage_layout_source']=dict(core_ready=core['ready'],adapter_failed=adapter['failed'],adapter_bytes=adapter['bytes'],core_bytes=core['bytes'])
    audit=rpc_guard(p,m)
    begin=len(p.rpc.log)
    def snap():
        out=ux.snap(h,p)
        out['cursor_cache']=h.u(0x205a2944,1)
        out['retry']=h.u(p.symbol_pc('n')+adapter['retry'],1)
        out['failed']=h.u(p.symbol_pc('n')+adapter['failed'],1)
        return out
    if name.startswith('h01_switch_'):
        original=p.rpc.call
        switched=[False]
        late=[]
        irqs=[]
        h.b.add_breakpoint(p.symbol_pc('rv_irq_save'),lambda b:irqs.append(dict(op='save',psw=b.core.psw)) or False)
        h.b.add_breakpoint(p.symbol_pc('rv_irq_restore'),lambda b:irqs.append(dict(op='restore',psw=b.core.psw,argument=b.core.r[0])) or False)
        def watch(event):
            if switched[0] and scope.touches_ui(event):
                late.append(dict(address=hex(event.address),pc=hex(event.pc),origin=event.origin,
                                 bytes=len(event.data),value=event.value))
        h.b.add_write_trace(0,2**32,watch)
        def call(cmd,value):
            if not switched[0]:
                other=shadow(h,v)
                if name.endswith('activity'):
                    other.run_slice(0x202ba380,0x202ba3c8)
                    other.leave_other_list()
                else:
                    ux.need(fr.native(other,0x202b0a74,(55,)))
                r['after_switch']=snap()
                r['after_switch']['state']=h.u(0x205d9c00)
                switched[0]=True
            return original(cmd,value)
        p.rpc.call=call
        h.parent()
        result,_,error=fr.publish(h,p,w)
        ux.need(result)
        assert error is None,error
        p.rpc.call=original
        r.update(result=result,late_ui_writes=late,irq_calls=irqs,after=snap(),psw_final=h.b.core.psw)
        dat_lo,dat_hi=p.image_base+256,p.image_base+256+len((TREE/'candidate/local/full-r13/engine.bin').read_bytes())
        r['DAT_late_ui_writes']=[x for x in late if dat_lo<=int(x['pc'],16)<dat_hi]
        assert switched[0] and not r['DAT_late_ui_writes']
        # The new rejection reaches restore before returning. Every save/restore
        # is paired in these synchronous samples; CB can change between calls.
        stack=[]
        for e in irqs:
            if e['op']=='save':stack.append(e['psw'])
            else:
                assert stack and stack.pop()==e['argument'],irqs
        assert not stack
    elif name in ('list_rollback','panel_rollback'):
        if name.startswith('panel'):
            ux.need(fr.native(h,0x202be220))
            ux.need(fr.native(h,0x202be220))
            ux.need(fr.native(h,0x202be220))
        r['before']=snap()
        r['triage_before']=triage_ui(h,p,core,adapter)
        original=p.rpc.call
        def busy(cmd,val):
            p.rpc.log.append(dict(cmd=cmd,value=val,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
            return -1
        p.rpc.call=busy
        failures=[]
        for _ in range(3):
            ux.need(fr.move_key(h,0x20))
            state=snap()
            assert state['cursor']==state['dot_row']==state['cursor_cache']==r['before']['cursor']
            assert state['rows']==r['before']['rows'] and state['W']==r['before']['W'] and state['failed']==0
            failures.append(state)
        p.rpc.call=original
        r['failures']=failures
        r['retry_event']=ux.need(fr.move_key(h,0x20,steps=30000000))
        r['triage_after_retry']=triage_ui(h,p,core,adapter)
        if name.startswith('panel'):
            try:
                r['legacy_cont_minus_1_match']=ux.matches(h,p,5,contrast=-1)
            except AssertionError as error:
                r['legacy_cont_minus_1_match']='AssertionError '+str(error.args)
            legacy_entry,_legacy_mapping=ux.expected_entry(p,5,-1)
            legacy_zero,_=ux.expected_entry(p,5,0)
            oracle_minus,mapping_minus,_e=triage_expected(m,p,5,[100,-1,0,0,0,0,0,0,0,0])
            oracle_zero,_,_e0=triage_expected(m,p,5,[100,0,0,0,0,0,0,0,0,0])
            diff_rows=[]
            for i in range(9):
                row=mapping_minus[32+12*i:44+12*i]
                nbytes,off=m.u16(row,4),m.u16(row,6)
                differing=[k for k in range(nbytes) if legacy_entry[off+k]!=oracle_minus[off+k]]
                diff_rows.append(dict(row=i,bytes=nbytes,legacy_vs_oracle_differing_bytes=len(differing)))
            r['triage_legacy_vs_oracle']=dict(cont0_legacy_equals_oracle=bytes(legacy_zero)==bytes(oracle_zero),
                cont0_differing_bytes=sum(1 for k in range(552) if legacy_zero[k]!=oracle_zero[k]),
                cont_minus1_rows=diff_rows,
                legacy_expected_row1_sha=None)
            r['new_oracle_actual_levels']=triage_compare(m,h,p,5,r['triage_after_retry']['levels'])
            r['new_oracle_cont_minus_1']=triage_compare(m,h,p,5,[100,-1,0,0,0,0,0,0,0,0])
            r['actual']=r['new_oracle_cont_minus_1']
            assert r['new_oracle_cont_minus_1']['rows_equal'] and r['new_oracle_actual_levels']['rows_equal']
        else:
            r['actual']=ux.matches(h,p,6)
        r['after']=snap()
        assert r['after']['retry']==0 and r['after']['cursor']==r['after']['dot_row']==r['after']['cursor_cache']
    elif name=='ready_warm':
        ux.need(fr.press(h,0x2b))
        p.ready=0
        ux.need(fr.native(h,0x200935b4,(0,)))
        h.parent()
        result,_,error=fr.publish(h,p,w)
        ux.need(result)
        assert error is None,error
        r['pending']=snap()
        r['unit_rpc_ready']=h.u(0x200d7fd8)
        r['engine_ready_legacy_offset_2523']=h.u(p.symbol_pc('g')+2523,1)
        r['engine_ready']=h.u(p.symbol_pc('g')+core['ready'],1)
        r['core_ready_offset']=core['ready']
        r['triage_pending']=triage_ui(h,p,core,adapter)
        assert r['unit_rpc_ready']==0 and r['engine_ready']==1 and r['pending']['rows']==7 and r['pending']['retry']==0
        assert not r['pending']['root']['ui_restore0']
        p.ready=1
        ux.need(fr.native(h,0x200935b4,(1,)))
        r['retry_event']=m.reopen(h,p,w)
        r['actual']=ux.matches(h,p,5)
        r['after']=snap()
    elif name=='settings_recheck':
        # This is a native settings input fault, separate from native menu state.
        value=h.u(h.settings+0x6dd,1)
        h.b.origin='model:settings_input'
        h.put(h.settings+0x6dd,1 if value!=1 else 2,1)
        r['before']=snap()
        m.reopen(h,p,w)
        r['actual']=ux.matches(h,p,5)
        r['after']=snap()
        assert r['after']['W']==r['before']['W']
    elif name=='write_latch':
        original=p.rpc.call
        fired=[False]
        def fail(cmd,val):
            if cmd==22 and not fired[0]:
                fired[0]=True
                original(cmd,val)
                p.rpc.log[-1].update(device_result=p.rpc.log[-1]['result'],result=-1,after_device_effect=True,simulated=True)
                return -1
            if fired[0]:
                p.rpc.log.append(dict(cmd=cmd,value=val,page=p.rpc.page,result=-1,t=p.rpc.t,simulated=True))
                return -1
            return original(cmd,val)
        p.rpc.call=fail
        r['failed_event']=ux.need(fr.move_key(h,0x20,steps=30000000))
        r['latched']=snap()
        r['triage_latched']=triage_ui(h,p,core,adapter)
        r['triage_rpc_counts']=dict(total=len(p.rpc.log)-begin,W=sum(1 for x in p.rpc.log[begin:] if x.get('cmd')==22))
        p.rpc.call=original
        assert fired[0] and r['latched']['failed']==1 and r['latched']['list']['uncertain']==1
        ux.need(fr.press(h,0x2b))
        h.parent()
        result,_,error=fr.publish(h,p,w)
        ux.need(result)
        assert error is None,error
        r['after']=snap()
        assert r['after']['rows']==8 and r['after']['cursor']==1 and r['after']['dot_row']==1
        at=len(p.rpc.log)
        ux.need(fr.move_key(h,0x20))
        ux.need(fr.native(h,0x202be220))
        assert len(p.rpc.log)==at
    elif name=='storage':
        R=pe.ROOT_ADDR
        session=h.u(R+56)
        caps=h.u(session+340)
        assert caps==0xe7fff
        records=[]
        def call(op,args):
            q,reply=pe.SCRATCH+0x300,pe.SCRATCH+0x380
            h.b.write(q,struct.pack('>HHI14I',1,64,0,*args))
            h.b.write(reply,bytes(32))
            h.put(R+6,1,1)
            try:
                result=p.call(p.symbol_pc('rv_call'),(1,op,q,reply),steps=2000000)
            finally:
                h.put(R+6,0,1)
            assert result['ok'],result
            status=h.u(reply+4)
            if status&0x80000000:status-=0x100000000
            records.append(dict(op=op,status=status,token=h.u(reply+16),capabilities=h.u(reply+24)))
            return records[-1]
        epoch=h.u(R+52)
        assert call(1,[0]*14)['capabilities']==3
        for op in (3,7,8,9):
            a=[0]*14
            a[0]=epoch;a[2]=1 if op==9 else 2;a[3]=1;a[5]=1 if op==9 else 4
            if op==3:a[8]=240
            if op==7:a[9]=2
            if op==9:a[3]=0;a[9]=5;a[10]=2
            assert call(op,a)['status']==-12
        a=[0]*14;a[0]=epoch;a[2]=1;a[5]=1
        opened=call(2,a)
        assert opened['status']==0 and opened['token']
        a=[0]*14;a[0]=epoch;a[1]=opened['token'];a[6]=p.image_base;a[7]=16
        assert call(5,a)['status']==-10
        a[6]=a[7]=0
        assert call(6,a)['status']==0
        r.update(storage_calls=records,capabilities=hex(caps),fixture='Direct service boundary supplies inflight only. No native UI state is seeded.')
    else:
        raise ValueError(name)
    r['RPC']=len(p.rpc.log)-begin
    r['rpc_log']=p.rpc.log[begin:]
    r['rpc_audit']=audit
    r['native_UI']=ui_audit(h)
    r['file_mutations']=m.no_writes(p)
    assert not r['native_UI']['host_ui_writes'] and not r['native_UI']['getter_callback_present']
    r['status']='PASS'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--only',nargs='+')
    args=parser.parse_args()
    args.generation=126;args.case='safety'
    fixture=prepare(args)
    names=args.only or ['h01_switch_activity','h01_switch_state','list_rollback','panel_rollback',
                        'ready_warm','settings_recheck','write_latch','storage']
    records=[]
    for name in names:
        sys.stdout.flush()
        pid=os.fork()
        if pid==0:
            r=dict(case=name,unit=args.unit)
            code=0
            try:
                run(name,fixture,r)
            except BaseException:
                r.update(status='EXECUTION_ERROR',error=traceback.format_exc());code=1
            save(f'local/safety/{args.unit}-{name}.json',r)
            print(name,r['status'],r.get('error','')[-500:],flush=True)
            os._exit(code)
        _,status=os.waitpid(pid,0)
        records.append(dict(case=name,wait_status=status))
    path=OUT/'evidence'/('safety-'+args.unit+'.json')
    previous=json.loads(path.read_text()).get('cases',[]) if args.only and path.exists() else []
    merged={row['case']:row for row in previous}
    merged.update({row['case']:row for row in records})
    records=list(merged.values())
    save(f'evidence/safety-{args.unit}.json',dict(status='PASS' if len(records)==8 and all(row['wait_status']==0 for row in records) else 'INCOMPLETE',
         dat_sha256=file_sha(DAT),cases=records,rerun_only=args.only))
    assert all(x['wait_status']==0 for x in records),records

if __name__=='__main__':
    main()
