"""Observe current and confirmed effect identities across refused choices."""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,snapshot,expected,exit_menu
from dat_format import sha,expand,expand_effect
from lock_checks import TRANSITIONS,set_source,configure
from apply_checks import ui_audit

def identities(cam):
    return dict(current=cam.engine_ref(),confirmed=cam.engine_ref('confirmed'),
                levels=cam.engine_bytes(H.LAYOUT['g.tweak'],20),
                confirmed_levels=cam.engine_bytes(H.LAYOUT['g.confirmed_tweak'],20),
                confirmed_valid=cam.engine_bytes(H.LAYOUT['g.confirmed_valid'],1))

def hashes(values):return {key:sha(value) for key,value in values.items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','mount'),default='mount');args=p.parse_args()
    result=dict(unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns(),cases=[]);tick=time.monotonic()
    try:
        cam=Camera(args.unit);cam.open_menu();active=configure(cam)
        for transition in TRANSITIONS:
            active['case']=None;key,target=set_source(cam,transition)
            cam.put_s(0x6dd,b'\x0a');cam.h.b.core.psw|=0x40
            before=snapshot(cam);refs=identities(cam);assert refs['confirmed_valid']==b'\x01'
            assert refs['current']==refs['confirmed'] and refs['levels']==refs['confirmed_levels']
            state=dict(timing='race-at-s',calls=[],stores=[],taken=False,armed=False,released=False)
            active['case']=state;cam.press(key)
            assert state['taken'] and identities(cam)==refs
            assert cam.unit_rows()==(before['rows'],before['T']) and cam.s_bytes(0,4096)==before['S']
            exit_menu(cam,'ok');cam.open_menu()
            assert identities(cam)==refs and cam.s_bytes(0,4096)==before['S']
            active['case']=None;cam.set_lock(-1)
            if transition=='effect-builtin':cam.goto(7);entry=expand(H.DAT_BYTES[cam.dat_path],H.UNITS[args.unit],8);effect=0
            else:
                cam.open_looks();cam.goto(0);cam.goto(target)
                entry=expand_effect(H.DAT_BYTES[cam.dat_path],target-1);effect=target
            current=identities(cam)
            assert current['current'][1]==entry[0] and current['current'][51]==effect
            assert current['current'][52:56]==(entry[4:8] if effect else bytes(4))
            assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry and cam.unit_rows()==expected(cam,entry)
            assert cam.s_bytes(0x6dd,2)==b'\x09\x09'
            settings=bytearray(before['S']);settings[0x36e]=1;settings[0x6dd:0x6df]=b'\x09\x09'
            settings[0xfd4:0xffc]=bytes(40) if effect else H.record_bytes(H.DAT_BYTES[cam.dat_path],8,H.UNITS[args.unit],[100]+[0]*9)
            assert cam.s_bytes(0,4096)==settings
            cam.press('OK');cam.open_menu();after=identities(cam)
            assert after['current']==after['confirmed'] and after['levels']==after['confirmed_levels']
            assert cam.s_bytes(0,4096)==settings
            result['cases'].append(dict(transition=transition,status='PASS',refused=hashes(refs),target=hashes(after),
                                        target_effect=effect,target_slot=entry[0],target_S_sha256=sha(settings),frame=cam.check_frame()))
            print('IDENTITY',args.unit,transition,'PASS',flush=True)
        result.update(status='PASS',native_UI_audit=ui_audit(cam))
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-tick)
        (HERE/'evidence'/f'identities-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)

if __name__=='__main__':main()
