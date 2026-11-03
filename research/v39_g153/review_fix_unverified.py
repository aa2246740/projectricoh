"""Actual prior-state snapshots before a first verified apply."""
from pathlib import Path
import argparse
import importlib.util
import json
import sys
import time
import traceback
import types

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import regressions as R
from native_support import Camera,H,snapshot,expected,exit_menu
from dat_format import expand,expand_effect,sha,u32
from lock_checks import TRANSITIONS,callback_return,serial
from apply_checks import ui_audit

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

sys.modules['g150_checks']=R.FIXED
C=load('review_checks',HERE/'legacy/review_checks.py')
D=types.ModuleType('decode')
D.modules=lambda raw:[dict(entries={s:expand(raw,u,s) for s in range(1,9)},refs=list(range(1,17))) for u in range(3)]
sys.modules['decode']=D
P=load('g152_previous_state_copy',HERE/'legacy/previous_state_checks.py')

def original_case(unit,kind):
    made=[]
    def camera(*a,**kw):
        cam=Camera(*a,**kw);made.append(cam);return cam
    H.Camera=camera
    try:
        try:
            cam,detail=P.check(unit,kind)
            assert kind!='late','The retired third-state expectation must fail.'
            detail['original_expectation']='PASS'
        except AssertionError as error:
            if kind!='late':raise
            trace=error.__traceback__
            while trace.tb_next:trace=trace.tb_next
            statement=Path(trace.tb_frame.f_code.co_filename).read_text().splitlines()[trace.tb_lineno-1].strip()
            assert statement=='assert taken and cam.unit_rows()==I.expected_rows(cam,stock_entry)',statement
            old=trace.tb_frame.f_locals
            assert old['taken'] and [(x['op'],x['returned']) for x in old['calls']]==[(6,0),(2,-2)]
            assert not old['stores'] and old['after']['W']-old['before']['W']==506
            cam=made[-1];prior=expand(H.DAT_BYTES[cam.dat_path],H.UNITS[unit],2)
            assert cam.unit_rows()==expected(cam,prior) and cam.s_bytes(0x36e,1)==b'\x04'
            frame=cam.check_frame();assert not frame['failed'],frame
            assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\x00'
            assert cam.engine_bytes(H.LAYOUT['g.snapshot_fault'],1)==b'\x00'
            exit_menu(cam,'ok');cam.open_menu();assert cam.unit_rows()==expected(cam,prior)
            assert cam.s_bytes(0x36e,1)==b'\x04' and not cam.check_frame()['failed']
            detail=dict(original_expectation='The unchanged OBSERVED_P1 assertion fails because the actual prior 02 state is retained.',
                        actual_prior_retained=True,frame=frame,reopened=cam.check_frame(),
                        retired_assertion=statement,calls=old['calls'],unit_W=506,S_stores=0,
                        copied_source_sha256=sha((HERE/'legacy/previous_state_checks.py').read_bytes()))
        detail['native_UI_audit']=ui_audit(cam)
        return detail
    finally:H.Camera=Camera

def contract_case(unit,transition,timing,exit_kind):
    cam=Camera(unit);raw=H.DAT_BYTES[cam.dat_path];u=H.UNITS[unit]
    source={'builtin-effect':expand(raw,u,2),'effect-same-base':expand_effect(raw,0),
            'effect-other-base':expand_effect(raw,1),'effect-builtin':expand_effect(raw,2)}[transition]
    target_number={'builtin-effect':1,'effect-same-base':2,'effect-other-base':3,'effect-builtin':8}[transition]
    target=expand(raw,u,8) if transition=='effect-builtin' else expand_effect(raw,target_number-1)
    if timing=='capture-invalid':
        invalid=bytearray(source);invalid[82]=255;source=bytes(invalid)
    P.set_unit_rows(cam,source);cam.put_s(0x36e,b'\x04');before_open=snapshot(cam)
    cam.open_menu();assert cam.unit_rows()==expected(cam,source) and cam.writes()==0
    assert cam.engine_bytes(H.LAYOUT['g.baseline'],1)==b'\x00'
    before=snapshot(cam);assert before['S']==before_open['S']
    cam.h.b.core.psw|=0x40;calls=[];selected=[];taken=[];stores=[];writes=[0];T_reads=[0];unit_changes=[]
    def target_input(b):
        if selected:return False
        selected.append(True);b.core.r[0]=target_number
        if transition!='effect-builtin':b.set_reg('pc',cam.symbol('uv_effect'))
        return False
    cam.h.b.add_breakpoint(cam.symbol('uv_preview'),target_input)
    def call(b):
        key=tuple(b.core.r[:2])
        if key[0]==6 and key[1] in (2,5,6):
            if key==(6,2) and timing in ('late','restore-fail') and not taken:
                assert b.core.psw&0x40;C.model_lock(cam,0);taken.append(True)
            row=dict(op=key[1]);calls.append(row)
            callback_return(cam,b,lambda current:row.update(returned=current.core.r[0] if current.core.r[0]<2**31 else current.core.r[0]-2**32))
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:stores.append(e.address-cam.s) if e.origin=='cpu' else None)
    original=cam.p.rpc.call
    def transport(cmd,value):
        if timing=='capture-race' and cmd==21 and cam.p.rpc.page==0x12c0:
            T_reads[0]+=1
            if T_reads[0]==3:
                changed=bytearray(source);changed[115]^=1;P.set_unit_rows(cam,changed)
                unit_changes.append('A unit model byte changes at the second snapshot read, before any W.')
        if cmd==22:writes[0]+=1
        if timing=='capture-fail' and cmd==21:return -1
        result=original(cmd,value)
        if timing=='restore-fail' and taken and cmd==22:return -1
        return result
    cam.p.rpc.call=transport
    if timing=='held':C.model_lock(cam,0)
    cam.press('DOWN');after=snapshot(cam);frame=cam.check_frame()
    assert selected
    fatal=timing in ('capture-fail','capture-invalid','capture-race','restore-fail')
    if fatal:
        assert frame['failed'] and frame['screen']==6,frame
        assert cam.engine_bytes(H.LAYOUT['g.snapshot_fault'],1)==b'\x01'
        assert cam.engine_bytes(H.LAYOUT['g.uncertain'],1)==b'\x01'
        assert after['S']==before['S'] and not stores
        if timing.startswith('capture-'):
            assert after['W']==before['W'] and cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\x00'
        if timing=='capture-race':assert T_reads[0]>=3 and len(unit_changes)==1
        for how in ('ok','half','menu'):
            exit_menu(cam,how);cam.open_menu();again=cam.check_frame()
            assert again['failed'] and cam.engine_bytes(H.LAYOUT['g.uncertain'],1)==b'\x01',again
            assert cam.s_bytes(0,4096)==before['S'] and not stores
    else:
        complete_target=cam.unit_rows()==expected(cam,target) and cam.s_bytes(0x36e,1)==b'\x01'
        complete_prior=cam.unit_rows()==(before['rows'],before['T']) and after['S']==before['S']
        assert complete_target or complete_prior,'Only the full target or actual complete prior state is permitted.'
        assert not frame['failed'],frame
        if timing in ('held','late'):assert complete_prior and not stores
        if timing=='idle':assert complete_target
        exit_menu(cam,exit_kind);cam.open_menu()
        assert cam.unit_rows()==expected(cam,target if complete_target else source)
        assert not cam.check_frame()['failed']
    return dict(transition=transition,timing=timing,exit=exit_kind,before=serial(before),after=serial(after),frame=frame,
                calls=calls,S_stores=stores,snapshot_T_reads=T_reads[0],unit_model_changes=unit_changes,native_UI_audit=ui_audit(cam),
                target_scope='An actual native key reaches uv_preview; only its target argument and, for effects, the effect entry function are supplied at that call boundary. No UI or engine memory is preset. This covers an unverified first transaction; the separate lock matrix covers physical Looks navigation.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True)
    p.add_argument('--original',choices=('held','idle','late'));p.add_argument('--transition',choices=TRANSITIONS)
    p.add_argument('--timing',choices=('held','idle','late','capture-fail','capture-invalid','capture-race','restore-fail'),default='late')
    p.add_argument('--exit',choices=('ok','half','menu'),default='ok');args=p.parse_args()
    name='original-'+args.original if args.original else args.transition+'-'+args.timing+'-'+args.exit
    result=dict(case=name,unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns());t=time.monotonic()
    try:
        result['details']=original_case(args.unit,args.original) if args.original else contract_case(args.unit,args.transition,args.timing,args.exit)
        result['status']='PASS'
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-t)
        (HERE/'evidence'/f'unverified-{args.unit}-{name}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

if __name__=='__main__':main()
