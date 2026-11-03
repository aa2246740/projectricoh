"""Effect knobs, final integer bytes and the target's pre-write refusal."""
from pathlib import Path
import argparse
import json
import struct
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dat_format import *
from format_checks import fix_effects
from math_reference import compute
from native_support import Camera,H,expected
from apply_checks import ui_audit
from ui_checks import callback_return,published_rows

def zero_y_fixture():
    raw=H.DAT.read_bytes();a,_=effect_area(raw);out=bytearray(raw);index=out[a+32+11]
    assert index&128
    start=a+32+32*u16(raw,a+8)+sum(align4(raw[a+16+k]*LENGTHS[k]) for k in range(3))+(index&127)*56
    out[start:start+6]=bytes(6);out[start+28:start+34]=bytes(6)
    for i in range(u16(raw,a+10)):
        e=expand_effect(out,i);struct.pack_into('>I',out,a+32+32*i+4,content_crc(e,out[a+32+32*i+18]))
    out=fix_effects(out);strict_effects(out)
    path=HERE/'local/variants/zero-y.DAT';path.write_bytes(out);return path

def field_value(cam,label):
    cam.press('DISP');assert cam.ui('screen')==1
    cam.press('DISP');assert cam.ui('screen')==2
    for _ in range(12):
        frame=cam.check_frame()
        if frame['labels'][frame['physical']].startswith(label):break
        cam.press('DOWN')
    else:raise AssertionError(label)
    cam.press('DISP');assert cam.ui('screen')==3

def verify(cam,effect):
    raw=H.DAT_BYTES[cam.dat_path];base=expand_effect(raw,effect-1)
    status,entry=compute(raw,H.UNITS[cam.unit],base,cam.levels());assert status==0
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
    assert cam.unit_rows()==expected(cam,entry) and cam.record()==bytes(40)
    return sha(entry)

def normal(unit):
    cam=Camera(unit);cam.open_menu();cam.open_looks();cam.select_effect(1)
    builtin_cache=bytes(cam.h.b.read(cam.adapter+H.LAYOUT['values'],160))
    rows=published_rows(cam);field_value(cam,'Warm');cam.press('UP');warm=cam.check_frame()
    assert warm['levels'][6]==1 and warm['effect']==1,warm
    first=verify(cam,1)
    cam.press('OK');cam.open_menu();cam.press('DISP')
    # Session memory keeps just the current effect's vector.
    cam.goto(1);assert cam.levels()[6]==1
    cam.goto(2);assert cam.levels()==[100]+[0]*9
    cam.goto(1);assert cam.levels()==[100]+[0]*9
    cam.goto(3);field_value(cam,'Filt');cam.press('UP');bw=cam.check_frame()
    assert bw['levels'][9]==1 and bw['effect']==3,bw
    second=verify(cam,3);assert cam.unit_rows()[0][2]==bytes(96)
    assert bytes(cam.h.b.read(cam.adapter+H.LAYOUT['values'],160))==builtin_cache
    cam.press('OK');cam.open_menu();cam.goto(4);builtin=cam.check_frame()
    assert builtin['effect']==0 and builtin['levels']==[100]+[0]*9,builtin
    entry=expand(H.DAT_BYTES[cam.dat_path],H.UNITS[unit],5)
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry and cam.unit_rows()==expected(cam,entry)
    assert all(n==8 for n in rows)
    return dict(warm=warm,warm_552_sha256=first,bw_filter=bw,bw_552_sha256=second,
                current_effect_only=True,builtin_cache_unchanged=True,builtin_after_effect=builtin,
                published_rows=rows,native_UI_audit=ui_audit(cam))

def refusal(unit):
    path=zero_y_fixture();cam=Camera(unit,dat=path);cam.open_menu();cam.open_looks();cam.select_effect(1)
    field_value(cam,'Warm');before=cam.unit_rows();S=cam.s_bytes(0,4096);writes=cam.writes();live=cam.engine_bytes(H.LAYOUT['g.live'],552)
    staging=cam.engine_bytes(H.LAYOUT['g.staging'],552);statuses=[];armed=[True]
    def enter(b):
        if armed[0]:callback_return(cam,b,lambda current:statuses.append(current.core.r[0] if current.core.r[0]<2**31 else current.core.r[0]-2**32))
        return False
    cam.h.b.add_breakpoint(cam.symbol('apply_stages'),enter)
    cam.press('UP');frame=cam.check_frame();armed[0]=False
    assert -2 in statuses,statuses
    assert cam.unit_rows()==before and cam.writes()==writes and cam.s_bytes(0,4096)==S
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==live and cam.engine_bytes(H.LAYOUT['g.staging'],552)==staging
    assert frame['levels'][6]==0 and not frame['failed'],frame
    reference,unchanged=compute(H.DAT_BYTES[path],H.UNITS[unit],expand_effect(H.DAT_BYTES[path],0),[100,0,0,0,0,0,1,0,0,0])
    assert reference==-2
    return dict(frame=frame,math_statuses=statuses,unit_W=0,S_stores=0,output_unchanged=True,
                variant_sha256=sha(path.read_bytes()),native_UI_audit=ui_audit(cam))

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=('normal','refusal'));p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');args=p.parse_args()
    result=dict(case=args.case,unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns());t=time.monotonic()
    try:result.update(status='PASS',details=(normal if args.case=='normal' else refusal)(args.unit))
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-t)
        (HERE/'evidence'/f'knobs-{args.case}-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
