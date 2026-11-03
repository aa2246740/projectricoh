"""Four effect transitions, native keys and g150 lock timing models."""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dat_format import expand,expand_effect,sha,u32
from native_support import Camera,H,snapshot,expected,exit_menu

TRANSITIONS=('builtin-effect','effect-same-base','effect-other-base','effect-builtin')
TIMINGS=('held','race-at-s','transient','record-busy','after-check-held','during-rows-release')
EXITS=('ok','half','menu')

def callback_return(cam,backend,callback):
    address=backend.core.r[14];active=[True]
    def returned(current):
        if active[0]:active[0]=False;callback(current)
        return False
    cam.h.b.add_breakpoint(address,returned)

def configure(cam):
    active={'case':None}
    def call(b):
        state=active['case']
        if state is None:return False
        service,op=b.core.r[:2]
        if service==6 and op in (2,5,6):
            state['calls'].append(dict(op=op,lock=cam.lock()))
            if state['timing']=='race-at-s' and op==2 and not state['taken']:
                state['taken']=True;b.origin='model:lock_owner_take';cam.set_lock(0);b.origin='cpu'
            if state['timing']=='transient' and op in (2,6):state['armed']=True
            if state['timing'] in ('after-check-held','during-rows-release') and op==6 and not state['taken']:
                def take(current):
                    assert current.core.r[0]==0 and current.core.psw&0x40
                    state['taken']=True;current.origin='model:lock_owner_take';cam.set_lock(0);current.origin='cpu'
                callback_return(cam,b,take)
        return False
    def restore(b):
        state=active['case']
        if state and state['timing']=='transient' and state['armed'] and not state['released']:
            def release(current):
                if state['released']:return
                assert current.core.psw&0x40
                state['released']=True;current.origin='model:lock_owner_release';cam.set_lock(-1);current.origin='cpu'
            callback_return(cam,b,release)
        return False
    def store(event):
        state=active['case']
        if state and event.origin=='cpu':state['stores'].append(dict(offset=event.address-cam.s,data=event.data.hex()))
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    cam.h.b.add_breakpoint(cam.symbol('rv_irq_restore'),restore)
    cam.h.b.add_write_trace(cam.s,cam.s+4096,store)
    original=cam.p.rpc.call
    def transport(cmd,value):
        answer=original(cmd,value);state=active['case']
        if state and state['timing']=='during-rows-release' and state['taken'] and cmd==22:
            state['unit_words']=state.get('unit_words',0)+1
            if state['unit_words']==8:
                state['released']=True;old=cam.h.b.origin;cam.h.b.origin='model:lock_owner_release'
                cam.set_lock(-1);cam.h.b.origin=old
        return answer
    cam.p.rpc.call=transport
    return active

def set_source(cam,transition):
    cam.set_lock(-1)
    # These are explicit S inputs, never native UI state. Production code
    # establishes all source rows, T, identity, memory and confirmation.
    cam.put_s(0x6dd,b'\x09\x09')
    if cam.h.u(0x2022f5ac,1)!=8:cam.open_menu()
    source={'builtin-effect':0,'effect-same-base':1,'effect-other-base':2,'effect-builtin':3}[transition]
    current=cam.engine_ref()
    if current[51]==source and (source or current[1]==8) and cam.engine_ref('confirmed')==current:
        # A refused prior case leaves this same native-confirmed source.
        # Reuse it and verify identity instead of applying it a second time.
        if transition=='effect-builtin':
            assert cam.ui('screen')==0;cam.goto(8);return 'UP',8
        if cam.ui('screen')==0:cam.goto(8);cam.press('DISP')
        assert cam.ui('screen')==7
        cam.goto(source)
        assert cam.ui('effect')==source
        return 'DOWN',source+1
    if not source:
        if cam.ui('screen')==7:cam.goto(0);cam.press('DISP')
        assert cam.ui('screen')==0
        cam.goto(7);cam.press('OK');cam.open_menu();cam.goto(8);cam.press('DISP')
    else:
        if cam.ui('screen')!=7:cam.goto(8);cam.press('DISP')
        cam.goto(source);cam.press('OK');cam.open_menu()
        if transition=='effect-builtin':
            assert cam.ui('screen')==0 and cam.ui('cur')==8 and cam.ui('effect')==source
            return 'UP',8
        cam.press('DISP');cam.goto(source)
    assert cam.ui('screen')==7 and cam.ui('cur')==source and cam.ui('effect')==source
    return 'DOWN',source+1

def serial(s):
    return dict(rows=[sha(x) for x in s['rows']],T=s['T'],S_sha256=sha(s['S']),ref_sha256=sha(s['ref']),effect=s['ref'][51],slot=s['ref'][1],W=s['W'])

def one(cam,active,transition,timing,exit_kind,label=''):
    active['case']=None;key,target=set_source(cam,transition)
    source_number={'builtin-effect':0,'effect-same-base':1,'effect-other-base':2,'effect-builtin':3}[transition]
    source_entry=expand(H.DAT_BYTES[cam.dat_path],H.UNITS[cam.unit],8) if not source_number else expand_effect(H.DAT_BYTES[cam.dat_path],source_number-1)
    assert cam.unit_rows()==expected(cam,source_entry)
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==source_entry
    entry=expand(H.DAT_BYTES[cam.dat_path],H.UNITS[cam.unit],8) if transition=='effect-builtin' else expand_effect(H.DAT_BYTES[cam.dat_path],target-1)
    target_rows=expected(cam,entry)
    if timing!='record-busy':cam.put_s(0x6dd,b'\x0a')
    cam.h.b.core.psw|=0x40
    cam.set_lock(-1 if timing in ('race-at-s','after-check-held','during-rows-release') else 0)
    state=dict(timing=timing,calls=[],stores=[],taken=False,armed=False,released=False)
    active['case']=state;before=snapshot(cam);started=time.time_ns();t=time.monotonic()
    cam.press(key);frame=cam.check_frame();after=snapshot(cam);key_calls=list(state['calls']);key_stores=list(state['stores'])
    if timing=='during-rows-release':
        assert state['taken'] and state['released'] and cam.unit_rows()==target_rows
        assert cam.s_bytes(0x6dd,2)==b'\x09\x09' and key_stores
        assert sum(x['op']==6 for x in key_calls)==sum(x['op']==2 for x in key_calls)==sum(x['op']==5 for x in key_calls)==1,key_calls
    elif timing=='record-busy':
        assert cam.unit_rows()==target_rows and after['S']==before['S'] and not key_stores
        assert sum(x['op']==5 for x in key_calls)==1 and not any(x['op'] in (2,6) for x in key_calls),key_calls
        assert cam.ui('effect')==(0 if transition=='effect-builtin' else target),frame
    else:
        assert cam.unit_rows()==(before['rows'],before['T']) and after['S']==before['S'] and after['ref']==before['ref']
        assert not key_stores and sum(x['op']==6 for x in key_calls)==1,key_calls
        if timing in ('race-at-s','after-check-held'):
            assert state['taken'] and sum(x['op']==2 for x in key_calls)==1 and after['W']>before['W']
        else:assert after['W']==before['W'] and not any(x['op']==2 for x in key_calls)
        if timing=='transient':assert state['released'] and cam.lock()==(-1,55)
    assert not frame['failed'],frame
    exit_menu(cam,exit_kind);closed=snapshot(cam);cam.open_menu();reopened=cam.check_frame();after_open=snapshot(cam)
    if timing=='during-rows-release':
        assert cam.unit_rows()==target_rows and cam.s_bytes(0x6dd,2)==b'\x09\x09'
    elif timing=='record-busy':
        assert cam.unit_rows()==target_rows and after_open['S']==before['S']
    else:
        assert cam.unit_rows()==(before['rows'],before['T']) and after_open['ref']==before['ref']
        assert closed['S']==before['S'] and after_open['S']==before['S']
    result=dict(status='PASS',transition=transition,timing=timing,exit=exit_kind,unit=cam.unit,
                dat_sha256=sha(H.DAT.read_bytes()),started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-t,
                before=serial(before),after_key=serial(after),after_exit=serial(closed),after_reopen=serial(after_open),
                key_calls=key_calls,key_S_stores=key_stores,frame=frame,reopened=reopened,
                source_setup='Native arrows and OK establish the confirmed source. Target movement and all exits also use native handlers.',
                S_input='WB 10 for a nonempty settings plan; unchanged 1/9/9 for record-busy. A refused choice preserves the actual S bytes through every exit and reopen.')
    active['case']=None
    prefix='lock-'+(label+'-' if label else '')
    path=HERE/'evidence'/f'{prefix}{cam.unit}-{transition}-{timing}-{exit_kind}.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',unit=cam.unit,transition=transition,timing=timing,exit=exit_kind,seconds=result['seconds'])),flush=True)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    p.add_argument('--transition',choices=TRANSITIONS);p.add_argument('--timing',choices=TIMINGS);p.add_argument('--exit',choices=EXITS)
    p.add_argument('--timings',nargs='+',choices=TIMINGS);p.add_argument('--exits',nargs='+',choices=EXITS)
    p.add_argument('--label',default='');p.add_argument('--summary')
    args=p.parse_args();started=time.time_ns();t=time.monotonic();results=[]
    assert not (args.timing and args.timings) and not (args.exit and args.exits)
    transitions=(args.transition,) if args.transition else TRANSITIONS
    timings=args.timings or ((args.timing,) if args.timing else TIMINGS)
    exits=args.exits or ((args.exit,) if args.exit else EXITS)
    assert not args.label or args.label.isalnum()
    try:
        cam=Camera(args.unit);cam.open_menu();active=configure(cam)
        for transition in transitions:
            for timing in timings:
                for exit_kind in exits:results.append(one(cam,active,transition,timing,exit_kind,args.label))
    except Exception:
        failure=dict(status='FAIL',unit=args.unit,error=traceback.format_exc(),started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-t)
        (HERE/'evidence'/f'lock-failure-{args.unit}.json').write_text(json.dumps(failure,indent=2)+'\n');raise
    summary=dict(status='PASS',unit=args.unit,cases=len(results),seconds=time.monotonic()-t,
                 transitions=list(transitions),timings=list(timings),exits=list(exits),label=args.label,
                 dat_sha256=sha(H.DAT.read_bytes()),started_ns=started,ended_ns=time.time_ns())
    assert len(results)==len(transitions)*len(timings)*len(exits)
    from apply_checks import ui_audit
    summary['native_UI_audit']=ui_audit(cam)
    (HERE/'evidence'/(args.summary or f'lock-matrix-{args.unit}.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
