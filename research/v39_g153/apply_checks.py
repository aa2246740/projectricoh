"""Compare full live entries, all S bytes and unit rows after real effect selection."""
from pathlib import Path
import argparse
import json
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dat_format import expand_effect,expand,sha
from native_support import Camera,H,expected

def ui_audit(cam):
    spans=((0x2022f71c,0x2022f740),(0x2022f5a8,0x2022f5b0),(0x205a279c,0x205a27dc),
           (0x205a280f,0x205a2810),(0x205d9bf8,0x205d9c04),(0x205a2944,0x205a2945))
    writes=[e for e in cam.h.writes if any(int(e['address'],16)<hi and int(e['address'],16)+e['size']>lo for lo,hi in spans)]
    bad=[e for e in writes if e['origin'] not in ('cpu','model:native_memset')]
    assert not bad,bad
    assert cam.h.b.__class__.__module__=='python_backend'
    assert not [e for e in cam.p.native_log if e.get('op') in ('create','write','rename','delete')]
    return dict(watched_writes=len(writes),host_UI_writes=len(bad),backend='tools/native_harness/python_backend.py')

def main():
    p=argparse.ArgumentParser();p.add_argument('--unit',choices=('50mm','28mm','mount'),required=True);args=p.parse_args()
    started=time.time_ns();t=time.monotonic();result=dict(unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=started,effects=[])
    try:
        cam=Camera(args.unit);cam.open_menu();cam.open_looks()
        for number in range(1,11):
            before=cam.s_bytes(0,4096);tick=time.monotonic();frame=cam.select_effect(number)
            entry=expand_effect(H.DAT_BYTES[cam.dat_path],number-1)
            assert cam.unit_rows()==expected(cam,entry)
            assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
            # Each base's complete S plan is Standard and WB 9/9. Effects
            # clear the existing known record; every other S byte is retained.
            settings=bytearray(before);settings[0x36e]=1;settings[0x6dd:0x6df]=b'\x09\x09';settings[0xfd4:0xffc]=bytes(40)
            actual=cam.s_bytes(0,4096);assert actual==settings,[hex(i) for i,(a,b) in enumerate(zip(actual,settings)) if a!=b]
            assert entry[20:115]==entry[456:551]
            if number==3:assert cam.unit_rows()[0][2]==bytes(96)
            result['effects'].append(dict(effect=number,status='PASS',live_552_sha256=sha(entry),S_sha256=sha(actual),
                                          frame=frame,seconds=time.monotonic()-tick))
            print('APPLY',args.unit,number,round(time.monotonic()-tick,3),flush=True)
        cam.press('OK');cam.open_menu();frame=cam.check_frame()
        assert frame['effect']==10 and frame['cur']==8
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==expand_effect(H.DAT_BYTES[cam.dat_path],9)
        result['native_UI_audit']=ui_audit(cam)
        saved=cam.s_bytes(0,4096)
        fresh=Camera(args.unit);stock=fresh.unit_rows();fresh.put_s(0,saved);writes=fresh.writes()
        fresh.open_menu();power=fresh.check_frame()
        assert fresh.unit_rows()==stock and fresh.writes()==writes and fresh.record()==bytes(40)
        assert power['slot']==4 and power['effect']==0 and power['cur']==3,power
        result.update(status='PASS',reopen=frame,power_cycle_model=dict(frame=power,unit_W=0,stock_rows_T=True),
                      fresh_native_UI_audit=ui_audit(fresh))
    except Exception:
        result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-t)
        (HERE/'evidence'/f'apply-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print('APPLY_RESULT',json.dumps({k:v for k,v in result.items() if k not in ('effects','reopen')}),flush=True)

if __name__=='__main__':main()
