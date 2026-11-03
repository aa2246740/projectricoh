"""新列表上的锁忙、退出与跨退出快照验证。"""
from pathlib import Path
import argparse
import json
import os
import sys
import time
import types
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,CONTROL,snapshot,expected,exit_menu,load
from dat_format import expand,sha
from verify import audit,published_rows
from scenes import P,C,LOCK,callback_return,SOURCES,entry


def busy(unit):
    cases=[]
    for target in (8,18):
        for timing in ('held','race-at-s','transient'):
            cam=Camera(unit);cam.open_menu();cam.goto(target-1);cam.press('OK');cam.open_menu()
            assert cam.ui('cur')==target-1
            active=LOCK.configure(cam);rows=published_rows(cam)
            cam.put_s(0x6dd,b'\x0a');cam.h.b.core.psw|=0x40
            cam.set_lock(-1 if timing=='race-at-s' else 0)
            state=dict(timing=timing,calls=[],stores=[],taken=False,armed=False,released=False)
            active['case']=state;calls=[]
            def call(b):
                if b.core.r[0]==6 and b.core.r[1] in (2,5,6):
                    row=dict(op=b.core.r[1]);calls.append(row)
                    callback_return(cam,b,lambda current:row.update(returned=current.core.r[0] if current.core.r[0]<2**31 else current.core.r[0]-2**32))
                return False
            cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
            before=snapshot(cam);cam.press('DOWN');frame=cam.check_frame();after=snapshot(cam)
            assert after['rows']==before['rows'] and after['T']==before['T'] and after['S']==before['S'] and after['ref']==before['ref']
            assert not state['stores'] and not frame['failed'] and frame['cur']==target-1
            assert [(x['op'],x['returned']) for x in calls]==([(6,0),(2,-2)] if timing=='race-at-s' else [(6,-2)]),calls
            if timing=='race-at-s':assert after['W']>before['W'] and state['taken']
            else:assert after['W']==before['W']
            if timing=='transient':assert state['released'] and cam.lock()==(-1,55)
            how='half' if timing=='race-at-s' else 'ok'
            exit_menu(cam,how);closed=snapshot(cam);cam.open_menu();reopened=snapshot(cam);cam.check_frame()
            for sample in (closed,reopened):
                for key in ('rows','T','S','ref'):assert sample[key]==before[key],(timing,key)
            assert not state['stores'] and all(x==8 for x in rows)
            cases.append(dict(target=target,timing=timing,exit=how,calls=calls,published_rows=rows,
                before=LOCK.serial(before),after=LOCK.serial(after),after_exit=LOCK.serial(closed),after_reopen=LOCK.serial(reopened),
                S_stores=state['stores'],audit=audit(cam)))
            active['case']=None
    return dict(cases=cases,shared_drivers=SOURCES)


def cross(unit):
    sys.modules['unverified_checks']=types.SimpleNamespace(P=P,C=C)
    sys.modules['apply_checks']=types.SimpleNamespace(ui_audit=audit)
    path=H.ROOT/'research/v39_g153/review_fix/legacy/independent_cases.py'
    source=path.read_text();old="assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\1'"
    assert source.count(old)==1
    changed=source.replace(old,"assert cam.engine_bytes(H.LAYOUT['g.live_verified'],1)==b'\\0'")
    module=types.ModuleType('g154_shared_cross');module.__file__=str(path)
    exec(compile(changed,str(path),'exec'),vars(module));module.OUT=HERE/('local/cross-control' if CONTROL else 'local/cross')
    (module.OUT/'runtime/evidence').mkdir(parents=True,exist_ok=True)
    cases=[]
    for slot in (4,8):
        result=module.after_refusal(unit,slot)
        assert result['matches']['actual_prior'] and not result['S_stores'] and not result['frame']['failed']
        cases.append(result)
    for kind in ('rows','T'):cases.append(module.snapshot_race(unit,kind))
    return dict(cases=cases,source_sha256=sha(source.encode()),executed_sha256=sha(changed.encode()),
        shared_drivers=SOURCES,amendment='仅把过期快照资格的旧预期 1 改为已修正合同的 0。')










def main():
    p=argparse.ArgumentParser();p.add_argument('group',choices=('busy','cross'))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');a=p.parse_args();tick=time.monotonic()
    detail=globals()[a.group](a.unit)
    result=dict(status='PASS',group=a.group,unit=a.unit,control=CONTROL,backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-tick,details=detail)
    suffix='-control' if CONTROL else ''
    (HERE/'evidence'/f'{a.group}-{a.unit}-{os.environ["GXR_HARNESS_BACKEND"]}{suffix}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',group=a.group,unit=a.unit,seconds=result['seconds'])))


if __name__=='__main__':main()
