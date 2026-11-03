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


def site(cam):
    sys.modules['v39_host']=H
    module=load(H.ROOT/'research/v39_g153/tests/dat_body.py','g154_h10_driver')
    return module.Site(cam)


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


def cards(unit):
    cam=Camera(unit);cam.open_menu();rows=published_rows(cam);ref=Reference(154);h10=site(cam);cases=[]
    for row in (2,8,18):
        cam.goto(row);before=wanted(cam,row,ref)
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==before
        assert h10.h10(0x23)==0x25
        cam.press('DISP');card=cam.check_frame();assert card['screen']==1
        assert h10.h10(0x23)==0x23
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==before
        cam.goto(1);cam.press('DISP');items=cam.check_frame();assert items['screen'] in (2,3),items
        if items['screen']==2:cam.press('DISP')
        value=cam.check_frame();assert value['screen']==3,value
        cam.press('UP');changed=cam.check_frame();entry=wanted(cam,row,ref)
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry and cam.unit_rows()==expected(cam,entry)
        cam.press('DISP')
        if cam.ui('screen')==2:cam.goto(0);cam.press('DISP')
        assert cam.ui('screen')==1
        cam.goto(0);cam.press('DISP');back=cam.check_frame();assert back['screen']==0 and back['cur']==row,back
        label=back['labels'][back['physical']];assert '*' in label,label
        cases.append(dict(row=row,card=card,value=value,changed=changed,back=back,H10_OK=0x25,live_552_sha256=sha(entry)))
    cam.goto(21);assert h10.h10(0x23)==0x23
    exit_menu(cam,'ok');cam.open_menu();reopened=cam.check_frame()
    assert reopened['cur']==20 and reopened['applied_user']==3,reopened
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==wanted(cam,20,ref)
    return dict(cases=cases,published_rows=rows,reopened=reopened,audit=audit(cam))


def equality():
    old=Reference(153);new=Reference(154)
    a=(H.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    b=H.DAT.read_bytes();records=[];directory=HERE/'evidence/outputs';directory.mkdir(exist_ok=True)
    for unit in range(3):
        for kind,number in [('builtin',i) for i in range(1,9)]+[('look',i) for i in range(1,11)]+[('user',i) for i in range(1,4)]:
            levels=[100]+[0]*9
            if kind=='look':abase,bbase=expand_effect(a,number-1),expand_effect(b,number-1)
            else:
                slot=number
                if kind=='user':slot,levels,_=user_record(b,number)
                abase,bbase=expand(a,unit,slot),expand(b,unit,slot)
            sa,pa=old.compute(a,unit,abase,levels);sb,pb=new.compute(b,unit,bbase,levels)
            assert sa==sb==0
            equal=pa==pb
            assert equal or (unit==2 and kind=='user' and bbase[0]!=4),(unit,kind,number)
            name=f'{unit}-{kind}-{number}'
            (directory/(name+'-g153.bin')).write_bytes(pa);(directory/(name+'-g154.bin')).write_bytes(pb)
            records.append(dict(unit=unit,kind=kind,number=number,equal=equal,old_sha256=sha(pa),new_sha256=sha(pb),changed_offsets=[i for i in range(552) if pa[i]!=pb[i]]))
    return dict(cases=records,builtin_equal=sum(x['equal'] for x in records if x['kind']=='builtin'),
        look_equal=sum(x['equal'] for x in records if x['kind']=='look'),user_equal=sum(x['equal'] for x in records if x['kind']=='user'))


def mount_knobs():
    cam=Camera('mount');cam.open_menu();ref=Reference(154);rows=published_rows(cam);cases=[]
    for slot,control,label,level in ((1,5,'Satu',6),(3,2,'High',8),(8,5,'Satu',8),
            (1,0,'Amt',125),(5,0,'Amt',120),(7,0,'Amt',120),(8,0,'Amt',125),(6,8,'Splt',1)):
        cam.goto(slot-1);cam.press('DISP');cam.goto(1);cam.press('DISP');assert cam.ui('screen')==2
        found=None
        for row in range(1,cam.ui('count')):
            cam.goto(row);frame=cam.check_frame()
            if frame['labels'][frame['physical']].startswith(label):found=row;break
        assert found is not None,(slot,label,cam.state())
        cam.press('DISP');assert cam.ui('screen')==3
        points=[];target=None
        for row in range(cam.ui('count')):
            cam.goto(row);frame=cam.check_frame();points.append(frame['levels'][control])
            if frame['levels'][control]==level:target=row
        assert target is not None,(slot,label,level,points)
        cam.goto(target);frame=cam.check_frame();wanted_entry=wanted(cam,slot-1,ref)
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==wanted_entry and cam.unit_rows()==expected(cam,wanted_entry)
        if label in ('Satu','High'):assert max(points)==level
        if control==0:
            expected_points=[150,125,100,75,50,25,0] if slot in (1,8) else [150,140,120,100,80,60,40,20,0]
            assert points==expected_points,(slot,points)
        if slot==6:assert wanted_entry[445:447]==bytes(2) and cam.unit_rows()[1]==0
        cases.append(dict(slot=slot,control=label,points=points,selected=level,frame=frame,live_552_sha256=sha(wanted_entry),T=cam.unit_rows()[1]))
        cam.press('DISP');cam.goto(0);cam.press('DISP');cam.goto(0);cam.press('DISP');assert cam.ui('screen')==0
    return dict(cases=cases,published_rows=rows,audit=audit(cam))


def main():
    p=argparse.ArgumentParser();p.add_argument('group',choices=('navigation','cards','equality','mount_knobs'))
    p.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm');a=p.parse_args()
    started=time.monotonic()
    detail=equality() if a.group=='equality' else mount_knobs() if a.group=='mount_knobs' else {'navigation':navigation,'cards':cards}[a.group](a.unit)
    result=dict(status='PASS',group=a.group,unit=a.unit,backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-started,details=detail)
    (HERE/'evidence'/f'{a.group}-{a.unit}-{os.environ["GXR_HARNESS_BACKEND"]}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',group=a.group,unit=a.unit,seconds=result['seconds'])))


if __name__=='__main__':main()
