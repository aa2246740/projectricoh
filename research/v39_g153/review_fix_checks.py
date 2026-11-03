"""Re-run the independent review cases and transaction lifetime variants."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time,traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,snapshot,expected,exit_menu
from dat_format import expand,expand_effect,sha
from unverified_checks import P,C
from lock_checks import serial,callback_return
from apply_checks import ui_audit

def copied_review(expired):
    source=HERE/'review_fix/legacy/independent_cases.py'
    original=source.read_text();text=original
    if expired:
        old="assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\1'"
        assert text.count(old)==1
        text=text.replace(old,"assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\0'")
    spec=importlib.util.spec_from_loader('g152_review_case_copy',loader=None)
    module=importlib.util.module_from_spec(spec);module.__file__=str(source)
    exec(compile(text,str(source),'exec'),module.__dict__)
    module.OUT=HERE/'local/review-fix-runtime'
    (module.OUT/'runtime/evidence').mkdir(parents=True,exist_ok=True)
    return module,dict(source_sha256=sha(original.encode()),executed_sha256=sha(text.encode()),
                       change='Only the expired snapshot qualification assertion changes from 1 to 0.' if expired else 'Unchanged review source.')

def two_transactions(unit,slot,observed=False):
    module,binding=copied_review(not observed)
    if observed:
        try:module.after_refusal(unit,slot)
        except AssertionError as error:
            assert str(error)=='The actual prior state changed after the first refused choice.',str(error)
        else:raise AssertionError('The frozen candidate must demonstrate the review failure.')
        result=json.loads((module.OUT/'runtime/evidence'/f'after-refusal-{slot}-{unit}-observation.json').read_text())
        assert not result['contract_pass'] and result['matches']['first_snapshot_02']
        return dict(observed_review_failure=result,review_binding=binding)
    result=module.after_refusal(unit,slot)
    assert result['matches']['actual_prior'] and not result['frame']['failed']
    for field in ('rows','T','S_sha256'):
        assert result['after'][field]==result['before'][field],field
        assert result['after_reopen'][field]==result['before'][field],field
    assert not result['S_stores']
    result['review_binding']=binding
    return result

def changed_state(unit,kind):
    cam=Camera(unit);raw=H.DAT_BYTES[cam.dat_path];u=H.UNITS[unit]
    first=expand(raw,u,2);P.set_unit_rows(cam,first);cam.put_s(0x36e,b'\x04')
    cam.open_menu();C.model_lock(cam,0);cam.press('DOWN')
    assert cam.unit_rows()==expected(cam,first) and cam.writes()==0
    assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\0'
    exit_menu(cam,'half' if kind=='photo' else 'ok')
    assert cam.h.u(0x2022f5ac,1)==7
    changes=[];all_stores=[]
    count=3 if kind=='multiple' else 1
    for attempt in range(count):
        entry=expand_effect(raw,attempt%3) if kind=='effect' else expand(raw,u,(8,4,3)[attempt%3])
        P.set_unit_rows(cam,entry);C.model_lock(cam,-1);cam.open_menu()
        assert cam.engine_bytes(H.LAYOUT['g.baseline'],1)==b'\0'
        before=snapshot(cam);cam.h.b.core.psw|=0x40;calls=[];taken=[];stores=[];active=[True]
        def call(b,active=active,calls=calls,taken=taken):
            if not active[0]:return False
            if b.core.r[0]==6 and b.core.r[1] in (2,5,6):
                op=b.core.r[1]
                if op==2 and not taken:C.model_lock(cam,0);taken.append(True)
                row=dict(op=op);calls.append(row)
                callback_return(cam,b,lambda current:row.update(returned=current.core.r[0] if current.core.r[0]<2**31 else current.core.r[0]-2**32))
            return False
        cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
        cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e,active=active,stores=stores:stores.append(e.address-cam.s) if active[0] and e.origin=='cpu' else None)
        cam.press('DOWN');after=snapshot(cam)
        assert taken and (2,-2) in [(x['op'],x['returned']) for x in calls]
        assert cam.unit_rows()==expected(cam,entry) and after['S']==before['S'] and not stores
        assert not cam.check_frame()['failed'] and cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\0'
        changes.append(dict(before=serial(before),after=serial(after),calls=calls))
        # Retire just this observer before the next independent key press.
        active[0]=False
        exit_menu(cam,'half' if kind=='photo' else 'ok')
        assert cam.s_bytes(0,4096)==before['S']
        all_stores.append(stores)
    C.model_lock(cam,-1);cam.open_menu();cam.press('DOWN')
    target=expand(raw,u,5)
    assert cam.unit_rows()==expected(cam,target) and not cam.check_frame()['failed']
    assert cam.engine_bytes(H.LAYOUT['g.baseline'],1)==b'\1'
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==target
    return dict(changes=changes,S_stores_during_refusals=all_stores,successful_final_entry_sha256=sha(target),
                final=serial(snapshot(cam)),native_UI_audit=ui_audit(cam),
                photo_scope='Native half-press exit, explicit closed-menu unit-row restoration with unchanged epochs, then the native constructor.' if kind=='photo' else None)

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('observed','after-refusal','effect','photo','multiple','snapshot-race'))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='mount');p.add_argument('--slot',type=int,default=8)
    p.add_argument('--race',choices=('T','rows'),default='rows');a=p.parse_args()
    result=dict(kind=a.kind,unit=a.unit,slot=a.slot,started_ns=time.time_ns(),dat_sha256=sha(H.DAT.read_bytes()));tick=time.monotonic()
    suffix=str(a.slot) if a.kind in ('observed','after-refusal') else a.race if a.kind=='snapshot-race' else 'state'
    try:
        if a.kind in ('observed','after-refusal'):detail=two_transactions(a.unit,a.slot,a.kind=='observed')
        elif a.kind=='snapshot-race':detail=copied_review(True)[0].snapshot_race(a.unit,a.race)
        else:detail=changed_state(a.unit,a.kind)
        result.update(status='PASS',detail=detail)
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'review_fix/evidence'/f'{a.kind}-{a.unit}-{suffix}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
if __name__=='__main__':main()
