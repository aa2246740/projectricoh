"""Eight physical rows across empty, long, error and ownership transitions."""
from pathlib import Path
import argparse
import copy
import json
import struct
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from dat_format import *
from format_checks import fix_effects,trust
from native_support import Camera,H,snapshot,exit_menu
from apply_checks import ui_audit

def published_rows(cam):
    rows=[]
    def call(b):
        if b.core.r[0]==10 and b.core.r[1] in (1,3):
            buffer=cam.h.u(b.core.r[2]+48);count=cam.h.u(buffer+20)
            rows.append(count);assert count==8,count
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    return rows

def rows_fixture():
    raw=H.DAT.read_bytes();a,n=effect_area(raw);out=bytearray(raw);area=bytearray(n)
    struct.pack_into('>4s6H',area,0,b'GXFX',1,32,48,48,32,0);area[16:20]=bytes((4,40,32,32))
    base=descriptor(raw,0,5);content=content_crc(expand(raw,0,5),7)
    for i in range(48):
        entry=bytearray(base[:18]+bytes((7,0))+f'L{i+1:011d}'.encode())
        struct.pack_into('>I',entry,4,content);area[32+32*i:64+32*i]=entry
    out[a:a+n]=area;out=fix_effects(out);strict_effects(out)
    path=HERE/'local/variants/rows49-same.DAT';path.write_bytes(out);return path

def list_case(unit,many):
    dat=rows_fixture() if many else HERE/'local/variants/empty.DAT'
    cam=Camera(unit,dat=dat);cam.open_menu();rows=published_rows(cam)
    cam.goto(8);cam.press('DISP');frame=cam.check_frame();frames=[frame]
    assert frame['screen']==7 and frame['count']==(49 if many else 1)
    if many:
        cam.press('UP');frames.append(cam.check_frame());assert cam.ui('cur')==48
        assert len(frames[-1]['labels'][-1])==13
        cam.press('DOWN');frames.append(cam.check_frame());assert cam.ui('cur')==0
        for target in (1,6,7,8,31,32,47,48):
            cam.goto(target);frames.append(cam.check_frame());assert cam.ui('cur')==target
            assert all(len(text)<=13 for text in frames[-1]['labels'])
        cam.press('DISP');title=cam.check_frame();assert title['labels'][0]=='<L00000000048',title
        frames.append(title);cam.goto(0);cam.press('DISP');assert cam.ui('screen')==7
    else:
        before=snapshot(cam)
        for key in ('UP','DOWN'):cam.press(key);frames.append(cam.check_frame());assert cam.ui('cur')==0
        assert cam.unit_rows()==(before['rows'],before['T']) and cam.s_bytes(0,4096)==before['S']
    exit_menu(cam,'ok');cam.open_menu();frames.append(cam.check_frame())
    assert rows and set(rows)=={8}
    return dict(frames=frames,published_rows=rows,native_UI_audit=ui_audit(cam),fixture_sha256=sha(dat.read_bytes()))

def error_case(unit):
    cam=Camera(unit);cam.open_menu();cam.open_looks();cam.select_effect(1);rows=published_rows(cam)
    original=cam.p.rpc.call;count=[0]
    def result(cmd,value):
        actual=original(cmd,value)
        if cmd==22:count[0]+=1;return -1
        return actual
    cam.p.rpc.call=result;cam.press('DOWN');frame=cam.check_frame()
    assert frame['failed']==1 and frame['screen']==6 and frame['labels'][0].startswith('ERR '),frame
    assert rows and set(rows)=={8} and count[0]>0
    return dict(frame=frame,published_rows=rows,unit_transport_failures=count[0],native_UI_audit=ui_audit(cam))

def name_case(unit):
    path=HERE/'local/variants/name12.DAT';cam=Camera(unit,dat=path);cam.open_menu();rows=published_rows(cam)
    cam.goto(10);menu=cam.check_frame()
    assert menu['labels'][-3:]==[' Looks',' MyRec',' DISP:Tw'],menu
    cam.open_looks();cam.select_effect(1);selected=cam.check_frame()
    name=bytes((33,34,35,36,37,38,39,40,41,43,45,63)).decode('ascii')
    assert selected['labels'][selected['physical']]=='>'+name,selected
    cam.press('DISP');title=cam.check_frame();assert title['labels'][0]=='<'+name,title
    assert len(title['labels'][0])==13 and all(n==8 for n in rows)
    return dict(menu_order=menu,selected=selected,title=title,published_rows=rows,native_UI_audit=ui_audit(cam),fixture_sha256=sha(path.read_bytes()))

def callback_return(cam,backend,callback):
    address=backend.core.r[14];active=[True]
    def returned(current):
        if active[0]:active[0]=False;callback(current)
        return False
    cam.h.b.add_breakpoint(address,returned)

def switch_parent(cam):
    assert cam.h.b.core.psw&0x40
    h=cam.h;h.b.map(0x206a0000,bytes(0x10000));backend=cam.m.v.PythonBackend()
    backend.regions,backend.mmio,backend.traces=h.b.regions,h.b.mmio,h.b.traces
    backend.breakpoints={key:list(value) for key,value in h.b.breakpoints.items()}
    backend.core.r,backend.core.psw=list(h.b.core.r),h.b.core.psw
    backend.core.cr=dict(h.b.core.cr);backend.core.bpsw=h.b.core.bpsw;backend.core.bbpsw=h.b.core.bbpsw;backend.core.acc=h.b.core.acc
    backend.set_reg('r15',0x206afff0);other=copy.copy(h);other.b=backend
    for address,args in ((0x201c092c,(2,1,0)),(0x202856d0,())):
        result=cam.m.fr.native(other,address,args,steps=30000000);assert result['ok'],result
    return cam.snapshot()

def ownership_case(unit):
    cam=Camera(unit);cam.open_menu();cam.open_looks();cam.select_effect(1)
    cam.h.b.core.psw|=0x40;before=snapshot(cam);rows=published_rows(cam);switched=[];stores=[]
    def call(b):
        if not switched and tuple(b.core.r[:2])==(11,1):
            callback_return(cam,b,lambda current:switched.append(switch_parent(cam)))
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),call)
    watched=((0x2022f5a8,0x2022f5b0),(0x2022f725,0x2022f727),(0x205a2944,0x205a2945))
    def store(e):
        if switched and e.origin=='cpu' and cam.p.image_base<=e.pc<cam.p.image_base+len(H.DAT_BYTES[cam.dat_path]):
            stores.append(dict(address=hex(e.address),data=e.data.hex()))
    for lo,hi in watched:cam.h.b.add_write_trace(lo,hi,store)
    cam.press('DISP');assert switched
    assert cam.unit_rows()==(before['rows'],before['T']) and cam.s_bytes(0,4096)==before['S'] and cam.writes()==before['W']
    assert cam.h.u(0x2022f5ac,1)==7 and all(x==8 for x in rows)
    assert [e['address'] for e in stores]==['0x2022f5a8','0x2022f5ac','0x2022f725','0x2022f726'],stores
    return dict(published_rows=rows,stock_after_release=7,after_release_stores=stores,
                inherited_cleanup='Same four native restore fields as g150.',native_UI_audit=ui_audit(cam))

def main():
    p=argparse.ArgumentParser();p.add_argument('case',choices=('empty','rows49','error','ownership','name12'))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');args=p.parse_args()
    result=dict(case=args.case,unit=args.unit,dat_sha256=sha(H.DAT.read_bytes()),started_ns=time.time_ns());t=time.monotonic()
    try:
        if args.case in ('empty','rows49'):result['details']=list_case(args.unit,args.case=='rows49')
        else:result['details']={'error':error_case,'ownership':ownership_case,'name12':name_case}[args.case](args.unit)
        result['status']='PASS'
    except Exception:result.update(status='FAIL',error=traceback.format_exc());raise
    finally:
        result.update(ended_ns=time.time_ns(),seconds=time.monotonic()-t)
        (HERE/'evidence'/f'ui-{args.case}-{args.unit}.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)

if __name__=='__main__':main()
