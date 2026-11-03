"""平铺导航、全量输出和 H10 一致行为的主机验证。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,CONTROL,expected,exit_menu,load
from dat_format import expand,expand_effect,strict_effects,u32,sha
from reference import Reference,user_record


def audit(cam):
    spans=((0x2022f71c,0x2022f740),(0x2022f5a8,0x2022f5b0),(0x205a279c,0x205a27dc),
           (0x205a280f,0x205a2810),(0x205d9bf8,0x205d9c04),(0x205a2944,0x205a2945))
    writes=[e for e in cam.h.writes if any(int(e['address'],16)<hi and int(e['address'],16)+e['size']>lo for lo,hi in spans)]
    bad=[e for e in writes if e['origin'] not in ('cpu','model:native_memset','model:stock_cursor')]
    assert not bad,bad
    assert not [e for e in cam.p.native_log if e.get('op') in ('create','write','rename','delete')]
    return dict(watched_writes=len(writes),unexpected_host_UI_writes=len(bad),native_stats=getattr(cam.h.b,'native_stats',{}))


def published_rows(cam):
    rows=[]
    def call(b):
        if b.core.r[0]==10 and b.core.r[1] in (1,3):
            buffer=cam.h.u(b.core.r[2]+48);count=cam.h.u(buffer+20)
            rows.append(count);assert count==8,count
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    return rows




def wanted(cam,row,ref):
    raw=H.DAT_BYTES[cam.dat_path];unit=H.UNITS[cam.unit]
    if row<8:base=expand(raw,unit,row+1)
    elif row<18:base=expand_effect(raw,row-8)
    elif row<21:
        slot,_,_=user_record(raw,row-17);base=expand(raw,unit,slot)
    else:return None
    status,entry=ref.compute(raw,unit,base,cam.levels());assert status==0
    return entry


def navigation(unit):
    cam=Camera(unit);cam.open_menu();rows=published_rows(cam);ref=Reference(154);frames=[]
    assert cam.ui('count')==22
    targets=list(range(22))+list(range(20,-1,-1)) if unit!='28mm' else [3,7,8,17,18,20,21,0]
    for row in targets:
        cam.goto(row);frame=cam.check_frame();assert frame['screen']==0 and frame['cur']==row
        assert all(len(text)<=13 and text.strip() not in ('Looks','MyRec') for text in frame['labels']),frame
        entry=wanted(cam,row,ref)
        if entry is not None:
            assert cam.unit_rows()==expected(cam,entry),(row,frame)
            assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry,(row,frame)
        label=frame['labels'][frame['physical']]
        if 8<=row<18:assert label[1:]==strict_effects(H.DAT_BYTES[cam.dat_path])['names'][row-8],label
        if 18<=row<21:assert label[1:]==user_record(H.DAT_BYTES[cam.dat_path],row-17)[2],label
        if row==21:assert label==' DISP:Tw',label
        frames.append(frame)
    cam.goto(21);cam.press('DOWN');assert cam.check_frame()['cur']==0
    cam.press('UP');assert cam.check_frame()['cur']==21
    assert rows and set(rows)=={8}
    return dict(frames=frames,wrap_both_ends=True,published_rows=rows,audit=audit(cam))








def main():
    p=argparse.ArgumentParser();p.add_argument('group',choices=('navigation',))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');a=p.parse_args()
    started=time.monotonic()
    detail=navigation(a.unit)
    result=dict(status='PASS',group=a.group,unit=a.unit,backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-started,details=detail)
    (HERE/'evidence'/f'{a.group}-{a.unit}-{os.environ["GXR_HARNESS_BACKEND"]}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',group=a.group,unit=a.unit,seconds=result['seconds'])))


if __name__=='__main__':main()
