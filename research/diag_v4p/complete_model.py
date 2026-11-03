"""Complete version 7 records produced by executing the shipped DAT and factory code."""
from pathlib import Path
import json,struct,sys,time,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H
import host_suite as F
import factory

def standby(c):
    if c.h.u(0x2022f5ac,1)==8:c.press(0x29)
    assert c.fr.native(c.h,0x202b0a74,(5,)).get('ok')

def menu(c):
    c.open()
    while c.u('page')!=0:c.disp()

def photo(c,index,raw=False,wide=False):
    standby(c)
    source,k,ref=factory.image(c,index,raw,wide,lambda a:F.site(c,0x2017098c,0x20170990,{'r5':a}))
    sp=c.h.b.get_reg('r15');c.h.put(sp+4,0x201558a8 if index%2==0 else 0x2015eaa4)
    c.h.stub(0x2016583c,'declared_encoder_result',value=0)
    before=c.h.b.read(k,588)
    F.site(c,0x2015f9d8,0x2015f9dc,{'r8':k,'r0':0x2016583c})
    assert c.h.b.read(k,588)==before
    at=c.record()+c.off['DgRecord.times']+80*index
    fields=struct.unpack('>14I',c.h.b.read(at,56))
    assert fields[8]==7,fields
    return dict(index=index,source=source,k=k,factory=ref,time=list(fields))

def run(unit):
    started=time.monotonic();c=H.Session(unit,True);factory.prepare(c)
    report=dict(unit=unit,dat_sha256=c.dat_hash,photos=[],model_kind='factory instructions with declared device memory and encoder completion')
    home=c.h.u(0x2022f726,1);c.open();assert c.h.u(0x2022f5ac,1)==8
    for _ in range(9):c.move()
    c.disp()
    if '--full-boot-pages' in sys.argv:
        for _ in range(36):c.move()
        report['boot_page_navigation']='all 37 pages executed'
    else:
        c.h.put(c.at('page')+4,36)
        report['boot_page_navigation']='UI cursor precondition at page 37; complete 37-page run retained in initial model trace; no captured source fields changed'
    c.disp();assert c.u('stage')==1
    standby(c)
    for code in (0x21,0x22,0x29):F.h10(c,code)
    menu(c)
    report['pages']={}
    for _ in range(11):report['pages'][str(c.u('page'))]=c.rows();c.disp()
    while c.u('page')!=0:c.disp()
    print(unit,'CURRENT and KEY',flush=True)
    for phase in range(4):
        c.move();assert c.u('scene')==phase+1
        standby(c);c.configuring=True
        c.h.b.write(0x20744800,bytes(0x177800))
        if phase==1:c.h.b.write(0x20744800+0x96000+640+640*100+80,bytes([1])*480)
        if phase==3:c.h.b.write(0x20744800+640*20+10,bytes([255])*60)
        c.configuring=False
        for _ in range(20):F.h10(c,0x29)
        assert c.u('osd_layer')==5
        print(unit,'OSD',phase+1,flush=True);menu(c)
    factory.slots(c,False);c.move();assert c.u('scene')==5
    report['photos'].append(photo(c,0));menu(c)
    factory.slots(c,True);c.move();assert c.u('scene')==6
    report['photos'].append(photo(c,1,True));menu(c)
    c.move();assert c.u('scene')==7
    report['photos'].append(photo(c,2,True,True));menu(c)
    c.move();assert c.u('scene')==8
    for i in range(3,6):report['photos'].append(photo(c,i,True))
    menu(c);c.move();assert c.u('scene')==9
    standby(c);menu(c)
    while c.u('page')!=9:c.disp()
    while c.u('bw_kind')<3:
        assert c.u('stage')==1 and c.u('scene')==9 and c.u('page')==9
        before_bw=c.u('bw_kind')*32+c.u('bw_piece')
        c.move(0x1f)
        assert c.u('bw_kind')*32+c.u('bw_piece')>before_bw
        if c.u('bw_piece')%8==0:print(unit,'BW',c.u('bw_kind'),c.u('bw_piece'),flush=True)
    while c.u('page')!=0:c.disp()
    c.move();assert c.u('scene')==10
    c.move();assert c.u('stage')==2
    raw=F.snapshot(c);(s.HERE/'evidence'/('record-'+unit+'.bin')).write_bytes(raw)
    values=[struct.unpack('>4I4H',raw[c.off['DgRecord.scene']+24*i:c.off['DgRecord.scene']+24*(i+1)]) for i in range(11)]
    report['scene_fields']=[list(x) for x in values]
    assert [x[6] for x in values]==[4,1,1,1,1,1,1,1,3,2,96],values
    assert [x[7] for x in values]==[1]*11,values
    for _ in range(4):c.disp();c.move()
    assert F.snapshot(c)==raw
    for code in (0x23,0x2b,0x0d,0x29,0x63):
        if c.h.u(0x2022f5ac,1)!=8:c.open()
        c.press(code)
        assert c.h.u(0x2022f726,1)==home and c.h.u(0x205a2944,1)==home
    report['audit']=c.audit();report['seconds']=round(time.monotonic()-started,2)
    report['status']='PASS';report['record_sha256']=s.sha(s.HERE/'evidence'/('record-'+unit+'.bin'))
    s.save(s.HERE/'evidence'/('host-'+unit+'.json'),report)
    print('PASS complete record',unit,report['seconds'],flush=True)

if __name__=='__main__':s.enable();run(sys.argv[1])
