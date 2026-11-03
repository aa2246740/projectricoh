"""Focused g152 checks on the Python native instruction backend."""
from pathlib import Path
import argparse
import json
import os
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dat_format import expand_effect,sha
from native_support import Camera,H,snapshot,expected,exit_menu

def smoke(unit):
    cam=Camera(unit);before=snapshot(cam)
    cam.open_menu();first=cam.check_frame()
    assert first['count']==11 and first['labels'][3]=='>4 Std',first
    assert snapshot(cam)['W']==before['W'] and cam.unit_rows()==(before['rows'],before['T'])
    looks=cam.open_looks();selected=cam.select_effect(1)
    assert selected['effect']==1 and cam.unit_rows()==expected(cam,expand_effect(H.DAT_BYTES[cam.dat_path],0))
    assert cam.record()==bytes(40) and cam.s_bytes(0x36e,1)==b'\1'
    cam.press('DISP');card=cam.check_frame();assert card['labels'][0]=='<M9 STD',card
    cam.goto(0);cam.press('DISP');back=cam.check_frame();assert back['screen']==7
    return dict(first=first,looks=looks,selected=selected,card=card,back=back)

def all_effects(unit):
    cam=Camera(unit);cam.open_menu();cam.open_looks();results=[]
    for effect in range(1,11):
        t=time.monotonic();frame=cam.select_effect(effect)
        entry=expand_effect(H.DAT_BYTES[cam.dat_path],effect-1)
        assert frame['effect']==effect and cam.unit_rows()==expected(cam,entry),(effect,frame)
        assert cam.s_bytes(0x36e,1)==b'\1' and cam.s_bytes(0x6dd,2)==b'\x09\x09'
        assert cam.record()==bytes(40) and cam.engine_ref()[51]==effect
        if effect==3:assert cam.unit_rows()[0][2]==bytes(96)
        results.append(dict(effect=effect,frame=frame,seconds=time.monotonic()-t,
                            row_sha256=[sha(b) for b in cam.unit_rows()[0]],T=cam.unit_rows()[1]))
    exit_menu(cam,'ok');closed=cam.unit_rows();cam.open_menu();reopen=cam.check_frame()
    assert cam.unit_rows()==closed and reopen['effect']==10 and reopen['cur']==8,reopen
    return dict(effects=results,reopen=reopen)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=('smoke','all-effects'))
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');args=parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    started=time.time_ns();t=time.monotonic()
    result=dict(case=args.case,unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=started)
    try:
        result['details']=(smoke if args.case=='smoke' else all_effects)(args.unit);result['status']='PASS'
    except Exception:
        result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(seconds=time.monotonic()-t,ended_ns=time.time_ns())
        (HERE/'evidence'/f'{args.case}-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

if __name__=='__main__':main()
