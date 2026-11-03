"""Additional native-path probes. No native UI state is seeded by the host."""
from pathlib import Path
import argparse
import copy
import json
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, save
import run_native as review
ux,m,fr,pe,v=review.ux,review.m,review.fr,review.pe,review.v
ACTIVE_GROUP='unspecified'
FOREIGN_AT=1
REOPEN_FN2=False

def start(unit):
    review.configure(unit,'adversarial-'+ACTIVE_GROUP+'-at'+str(FOREIGN_AT))
    h,p,w=m.boot(unit);m.published(h,p,w);ins=ux.instrument(h,p)
    crc=p.symbol_pc('gxr2_crc_add');callbacks=h.b.breakpoints[crc].copy()
    ux.arm_entries(h,p,ins);h.b.breakpoints[crc]=callbacks
    return h,p,w,ins

def move_to(h,p,row):
    for _ in range(8):
        current=h.u(0x2022f726,1)
        if current==row:return
        ux.need(fr.move_key(h,0x20));ux.matches(h,p,h.u(0x2022f726,1))
    raise AssertionError(row)

def service_trace(h,p):
    rows=[];pending=[];returns=set()
    def returned(b):
        if not pending or pending[-1]['return_pc']!=b.get_reg('pc'):return False
        row=pending.pop();row['status']=b.get_reg('r0');row['reply_status']=int.from_bytes(b.read(row['reply']+4,4),'big',signed=True)
        row['reply_token']=h.u(row['reply']+16)
        if row['id']==6 and row['operation']==1 and row['buffer']:row['settings_token']=h.u(row['buffer']+8)
        row['returned']=True;return False
    def entry(b):
        sid,op,q,reply=b.core.r[:4]
        if sid not in (4,5,6,10):return False
        row=dict(sequence=len(rows),id=sid,operation=op,reply=reply,buffer=h.u(q+48),
                 return_pc=b.get_reg('r14'),returned=False)
        rows.append(row);pending.append(row)
        if row['return_pc'] not in returns:
            returns.add(row['return_pc']);h.b.add_breakpoint(row['return_pc'],returned)
        return False
    h.b.add_breakpoint(p.symbol_pc('rv_call'),entry)
    return rows

def recovery(unit,r):
    h,p,w,ins=start(unit);move_to(h,p,3);ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
    # Reopen retains CRC acceleration. RPC callbacks record the actual address
    # before each command, including a W that crosses the selected X page.
    before=ux.snap(h,p);services=service_trace(h,p);trace=[];applies=[];original=p.rpc.call
    def applied(b):
        applies.append(dict(index=len(trace),recovery=b.get_reg('r2'),confirm=b.get_reg('r3'),slot=h.u(b.get_reg('r0')+1,1)))
        return False
    h.b.add_breakpoint(p.symbol_pc('apply_impl'),applied)
    count=0
    def call(cmd,value):
        nonlocal count
        count+=1;cursor=p.rpc.cursor;page=p.rpc.page
        result=original(cmd,value)
        injected=count==16
        if injected:p.rpc.log[-1].update(device_result=result,result=-1,injected=True);result=-1
        address=((page or 0)<<16)|(value&0xfffe) if cmd==21 else cursor if cmd==22 else None
        trace.append(dict(index=len(trace),cmd=cmd,value=value,page_before=page,page_after=p.rpc.page,address=address,result=result,injected=injected))
        return result
    p.rpc.call=call
    ux.need(fr.move_key(h,0x20));p.rpc.call=original
    actual=ux.matches(h,p,3);after=ux.snap(h,p)
    assert after['list']['uncertain']==0 and after['cursor']==3
    begin=next(x['index'] for x in applies if x['recovery']==1)
    recovery_calls=trace[begin:]
    entry,mapping=ux.expected_entry(p,3)
    row_proofs=[];crossings=[]
    for i in range(9):
        row=mapping[32+12*i:44+12*i];address=m.u32(row,0);n=m.u16(row,4)
        required=list(range(address&~1,(address+n+1)&~1,2))
        writes=[x for x in recovery_calls if x['cmd']==22 and x['address'] in required]
        assert sorted(x['address'] for x in writes)==required,(i,'not a full row rewrite')
        last_write=max(x['index'] for x in writes)
        reads=[x for x in recovery_calls if x['cmd']==21 and x['address'] in required and x['index']>last_write]
        assert sorted(x['address'] for x in reads)==required,(i,'not every word read back')
        for x in reads:
            assert 0<=x['value']<=65535 and x['page_before']==x['address']>>16
            assert x['result']==p.rpc.half(x['address'])
        for j,x in enumerate(reads[1:],1):
            if reads[j-1]['address']>>16!=x['address']>>16:
                preceding=trace[x['index']-1]
                assert preceding['cmd']==23 and preceding['value']==x['address']>>16
                crossings.append(dict(previous=hex(reads[j-1]['address']),next=hex(x['address']),X=preceding,V=x))
        row_proofs.append(dict(row=i,address=hex(address),bytes=n,halfwords=len(required),W=len(writes),V=len(reads)))
    settings=[x for x in services if x['id']==6]
    assert settings and all(x['returned'] and x['reply_status']==0 for x in settings)
    active=False;tokens=[]
    for x in settings:
        if x['operation']==1:
            assert not active and x['settings_token'];active=True;tokens.append(x['settings_token'])
        elif x['operation']==2:assert active
        elif x['operation']==3:assert active;active=False
    assert not active
    r.update(status='PASS',before=before,after=after,actual=actual,apply_entries=applies,
             rows=row_proofs,page_crossings=crossings,RPC_trace=trace,service_trace=services,settings_tokens=tokens,
             file_mutations=m.no_writes(p))
    print('PASS',unit,'nine complete rows rewritten and every halfword read back; settings tokens balanced; crossings',len(crossings),flush=True)

def exits(unit,r):
    h,p,w,ins=start(unit);cases=[];r['confirm_cases']=cases
    for keep in (0,1):
        for event in (0x23,0x2b):
            m.reopen(h,p,w);move_to(h,p,3)
            # Execute the official flag setter; do not write 0x2037F2FE.
            ux.need(fr.native(h,0x20265818,(keep,)))
            assert h.u(0x2037f2fe,1)==keep
            at=len(ins['events']);rpc=len(p.rpc.log);before=ux.snap(h,p)
            result=ux.need(fr.press(h,event));after=ux.snap(h,p);events=ins['events'][at:]
            case=dict(keep=keep,event=hex(event),before=before,after=after,native_result=result,events=events,rpc_delta=len(p.rpc.log)-rpc)
            cases.append(case);save('native/adversarial-exits-progress-'+unit+'.json',r)
            print('OBSERVED H07',hex(event),'keep',keep,'confirmed',after['list']['confirmed_slot'],'root',after['root']['state'],'events',events,flush=True)
            assert len(events)==1 and events[0]['caller']==('0x202c2d74' if keep else '0x202c2d84'),events
            assert events[0]['keep']==keep and int(events[0]['raw'],16)==event
            assert after['list']['confirmed_valid'] and after['list']['confirmed_slot']==3
            assert len(p.rpc.log)==rpc
            if keep:assert after['list']['opened']==1 and after['rows']==8
            else:assert after['native_overlay']==0 and after['list']['opened']==0
            ux.matches(h,p,3)
            print('PASS native H07',hex(event),'keep',keep,'caller',events[0]['caller'],flush=True)
    # Both genuine half-shutter top-level columns and the native helper are
    # executed. A helper entry is explicitly not a physical key-delivery test.
    half=[]
    for address,key in ((0x2029fdc4,0x29),(0x202bd724,0x29),(0x2029fdc4,0x63),(0x202bd724,0x63),(0x202be978,0x29),(0x202be978,0x63)):
        m.reopen(h,p,w);move_to(h,p,3);h.select_item_8()
        ux.need(fr.native(h,0x20265818,(0,)))
        at=len(ins['events']);result=fr.native(h,address,(key,0),steps=8000000)
        row=dict(entry=hex(address),key=hex(key),result=result,state=ux.snap(h,p),events=ins['events'][at:])
        half.append(row)
        if result.get('ok'):row['actual']=ux.matches(h,p,3)
        print('HALF',hex(address),hex(key),'ok',result.get('ok'),'H07',row['events'],flush=True)
    r.update(status='PASS' if all(x['result'].get('ok') for x in half) else 'PARTIAL_NATIVE_BLOCK',
             confirm_cases=cases,half_cases=half,file_mutations=m.no_writes(p),native_log=p.native_log)

def nested(unit,r):
    cases=[]
    for key in (0x23,0x2b,0x29):
        h,p,w,ins=start(unit);before=ux.snap(h,p)
        h.b.map(0x206a0000,bytes(0x10000));original=p.rpc.call;schedule={'fired':False}
        def call(cmd,value):
            if not schedule['fired']:
                schedule['fired']=True;b=v.PythonBackend();b.regions=h.b.regions;b.mmio=h.b.mmio;b.traces=h.b.traces
                b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()};b.core.r=list(h.b.core.r)
                b.core.psw=h.b.core.psw;b.core.cr=dict(h.b.core.cr);b.core.bpsw=h.b.core.bpsw;b.core.bbpsw=h.b.core.bbpsw;b.core.acc=h.b.core.acc
                b.set_reg('r15',0x206afff0);shadow=copy.copy(h);shadow.b=b
                at=len(ins['events']);schedule['resident_inflight']=h.u(pe.ROOT_ADDR+6,1)
                schedule['native_result']=fr.press(shadow,key) if key!=0x29 else fr.native(shadow,0x2029fdc4,(key,0),steps=8000000)
                schedule['nested_engine_entries']=ins['events'][at:];schedule['after_nested']=ux.snap(h,p)
            return original(cmd,value)
        p.rpc.call=call;result=fr.move_key(h,0x20);p.rpc.call=original
        slots=[]
        for slot in range(1,9):
            try:ux.matches(h,p,slot)
            except AssertionError:pass
            else:slots.append(slot)
        row=dict(event=hex(key),before=before,schedule=schedule,outer=result,after=ux.snap(h,p),complete_slots=slots,file_mutations=m.no_writes(p))
        cases.append(row)
        print('NESTED',hex(key),'complete slots',slots,'state',row['after']['root']['state'],flush=True)
    r.update(status='OBSERVED',cases=cases)

def foreign(unit,r):
    h,p,w,ins=start(unit);h.b.map(0x206a0000,bytes(0x10000));original=p.rpc.call
    state={'fired':False,'rpc_seen':0,'inject_at':FOREIGN_AT};writes=[];previews=[]
    def preview_entry(b):
        previews.append(dict(slot=b.get_reg('r0'),after_takeover=state['fired']))
        return False
    h.b.add_breakpoint(p.symbol_pc('preview_cached'),preview_entry)
    def watch(ev):
        if ev.address in (0x205a293c,0x205a2944,0x2022f725,0x2022f726,0x2022f5a8,0x2022f5ac,0x2037f3bc):
            writes.append(dict(address=hex(ev.address),data=ev.data.hex(),pc=hex(ev.pc)))
    h.b.add_write_trace(0,2**32,watch)
    def call(cmd,value):
        state['rpc_seen']+=1
        if not state['fired'] and state['rpc_seen']==FOREIGN_AT:
            state['fired']=True;b=v.PythonBackend();b.regions=h.b.regions;b.mmio=h.b.mmio;b.traces=h.b.traces
            b.breakpoints={k:list(x) for k,x in h.b.breakpoints.items()};b.core.r=list(h.b.core.r)
            b.core.psw=h.b.core.psw;b.core.cr=dict(h.b.core.cr);b.core.bpsw=h.b.core.bpsw;b.core.bbpsw=h.b.core.bbpsw;b.core.acc=h.b.core.acc
            b.set_reg('r15',0x206afff0);shadow=copy.copy(h);shadow.b=b
            state['before_native']=ux.snap(h,p);state['resident_inflight']=h.u(pe.ROOT_ADDR+6,1)
            # The same genuine alternate ADJ-list constructor is used by the
            # original harness. No list row, view pointer or activity is seeded.
            shadow.run_slice(0x202ba380,0x202ba3c8)
            shadow.leave_other_list();state['after_native']=ux.snap(h,p)
            state['native_type_after_constructor']=h.u(0x2022f71c,1)
            state['view_epoch_after_constructor']=h.u(pe.ROOT_ADDR+32)
            state['native_state_pointer']=hex(h.u(0x205a293c));state['native_cached_cursor']=h.u(0x205a2944,1)
            state['write_mark_after_native']=len(writes)
        return original(cmd,value)
    p.rpc.call=call;result=fr.move_key(h,0x20);p.rpc.call=original
    slots=[]
    for slot in range(1,9):
        try:ux.matches(h,p,slot)
        except AssertionError:pass
        else:slots.append(slot)
    r.update(status='OBSERVED',schedule=state,outer=result,after=ux.snap(h,p),complete_slots=slots,
             writes=writes,events=copy.deepcopy(ins['events']),preview_entries=copy.deepcopy(previews),dat_sha256=m.sha(m.DAT.read_bytes()),file_mutations=m.no_writes(p))
    assert state['fired'] and result.get('ok'),r
    assert not writes[state['write_mark_after_native']:],writes[state['write_mark_after_native']:]
    assert r['after']['cursor']==state['after_native']['cursor']
    assert r['after']['dot_row']==state['after_native']['dot_row']
    assert r['after']['native_activity']==7 and r['after']['native_overlay']==21
    assert r['after']['root']['state']==3 and not r['after']['list']['uncertain']
    assert len(previews)==1 and previews[0]['slot']==5 and not previews[0]['after_takeover']
    if FOREIGN_AT==1:
        assert slots==[4] and r['after']['W']==0 and r['after']['preview_calls']==0
        assert r['after']['deep_sha256']==state['after_native']['deep_sha256']
    else:assert slots==[5]
    # Continue the foreign native UI without select_item_8(), which the
    # convenience press() helper deliberately does for Image-only tests.
    entries=len(ins['events']);calls=p.visited('core_call');unit_state=r['after']['deep_sha256']
    follow=[ux.need(fr.move_key(h,0x20)),ux.need(fr.native(h,0x202c2abc,(0x2b,),steps=8000000))]
    r['foreign_followthrough']=dict(native=follow,state=ux.snap(h,p),new_engine_entries=len(ins['events'])-entries,
        new_engine_core_calls=p.visited('core_call')-calls)
    assert r['foreign_followthrough']['new_engine_entries']==0
    assert r['foreign_followthrough']['new_engine_core_calls']==0
    assert r['foreign_followthrough']['state']['deep_sha256']==unit_state
    if REOPEN_FN2:
        h.parent();m.published(h,p,w);slot=h.u(0x2022f726,1)
        ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b))
        r['reopened_fn2']=dict(slot=slot,state=ux.snap(h,p))
        assert r['reopened_fn2']['state']['root']['state']==3,r['reopened_fn2']
        r['reopened_fn2']['actual']=ux.matches(h,p,slot,contrast=1)
        m.reopen(h,p,w);assert h.u(0x2022f726,1)==slot
    r['status']='PASS'
    print('FOREIGN native constructor rows',state['after_native']['rows'],'cursor',state['after_native']['cursor'],
          'final rows',r['after']['rows'],'cursor',r['after']['cursor'],'complete slots',slots,flush=True)

def fallback(unit,r):
    h,p,w,ins=start(unit)
    ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b))
    r['modified04']=ux.matches(h,p,4,contrast=1)
    m.reopen(h,p,w);ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b));m.reopen(h,p,w);ux.matches(h,p,5)
    fail,original=ux.injected_rpc(p,16,after_write=True,extra_failures=(22,))
    ux.need(fr.move_key(h,0x20));p.rpc.call=original
    assert len(fail['events'])==2 and h.u(0x2022f726,1)==4
    r['restored']=ux.matches(h,p,4);before=len(p.rpc.log);refresh=h.stub_hits.get('preview',0)
    ux.need(fr.press(h,0x2b))
    r['confirmation']=dict(extra_rpc=len(p.rpc.log)-before,extra_refresh=h.stub_hits.get('preview',0)-refresh,
        state=ux.snap(h,p),actual=ux.matches(h,p,4))
    assert not r['confirmation']['extra_rpc'] and not r['confirmation']['extra_refresh']
    m.reopen(h,p,w);r['reopened']=ux.snap(h,p);assert r['reopened']['cursor']==4
    ux.matches(h,p,4);r.update(status='PASS',file_mutations=m.no_writes(p))
    print('PASS pure04 fallback accepts actual zero tweak; old cached contrast+1 is not reapplied',flush=True)

def main():
    global ACTIVE_GROUP,FOREIGN_AT,REOPEN_FN2
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=('recovery','exits','nested','foreign','fallback'));parser.add_argument('unit',choices=('50mm','28mm','mount'))
    parser.add_argument('--at',type=int,default=1)
    parser.add_argument('--reopen-fn2',action='store_true')
    args=parser.parse_args();FOREIGN_AT=args.at;REOPEN_FN2=args.reopen_fn2;ACTIVE_GROUP=args.group;r=dict(unit=args.unit,group=args.group,native_ui_hand_seeded=False)
    try:globals()[args.group](args.unit,r)
    except Exception:r['status']='FAIL';r['error']=traceback.format_exc();raise
    finally:save('native/adversarial-'+args.group+'-'+args.unit+('-at'+str(args.at) if args.group=='foreign' else '')+('-reopen-fn2' if args.reopen_fn2 else '')+'.json',r)

if __name__=='__main__':main()
