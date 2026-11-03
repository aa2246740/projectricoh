"""独立抽查新行、数量边界、错误返回和原厂续接。"""
from pathlib import Path
import ctypes as C
import json
import os
import struct
import sys
import time

import review_support as R
from dat_format import expand, expand_effect, effect_area, seal, strict_effects, u32, crc, content_crc, CRC_FIELDS

H, Camera = R.H, R.Camera


def compact(cam):
    s=R.N.snapshot(cam)
    return dict(unit_sha256=R.digest(b''.join(s['rows'])+s['T'].to_bytes(2,'big')),
                S_sha256=R.digest(s['S']), reference=s['ref'].hex() if s['ref'] else None,
                W=s['W'], native=R.CC.native(cam), frame=cam.state())


def observe_rows(cam):
    result=[]
    def publication(b):
        if b.core.r[0]==10 and b.core.r[1] in (1,3):
            buf=cam.h.u(b.core.r[2]+48)
            count=cam.h.u(buf+20)
            labels=cam.labels()
            assert count==8 and len(labels)==8 and all(len(x)<=13 for x in labels),(count,labels)
            result.append(dict(rows=count,labels=labels))
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),publication)
    return result


def equality(unit):
    old,new=R.REF.Reference(153),R.REF.Reference(154)
    a=(R.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    b=(R.ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    out=R.OUT/'evidence/outputs';out.mkdir(exist_ok=True)
    cases=[]
    for m in range(3):
        for kind,count in [('builtin',8),('look',10),('user',3)]:
            for number in range(1,count+1):
                levels=[100]+[0]*9
                if kind=='look':
                    abase,bbase=expand_effect(a,number-1),expand_effect(b,number-1)
                else:
                    slot=number
                    if kind=='user':slot,levels,name=R.REF.user_record(b,number)
                    abase,bbase=expand(a,m,slot),expand(b,m,slot)
                sa,pa=old.compute(a,m,abase,levels);sb,pb=new.compute(b,m,bbase,levels)
                assert sa==sb==0 and len(pa)==len(pb)==552
                stem=f'{m}-{kind}-{number}'
                (out/(stem+'-g153.bin')).write_bytes(pa);(out/(stem+'-g154.bin')).write_bytes(pb)
                different=[i for i in range(552) if pa[i]!=pb[i]]
                cases.append(dict(unit=m,kind=kind,number=number,levels=levels,equal=not different,
                                  changed_offsets=different,old_sha256=R.digest(pa),new_sha256=R.digest(pb)))
    changed=[x for x in cases if not x['equal']]
    assert len(changed)==2 and all(x['unit']==2 and x['kind']=='user' for x in changed),changed
    return dict(cases=cases,unchanged=61,changed=changed,request_bytes=C.sizeof(R.REF.Request))


def busy(unit):
    cases=[]
    for target,timing in ((8,'held'),(17,'race-at-s'),(18,'race-at-s'),(20,'transient')):
        cam=Camera(unit);cam.open_menu();cam.goto(target-1);cam.press('OK');cam.open_menu()
        assert cam.ui('cur')==target-1
        active=R.SC.LOCK.configure(cam);published=observe_rows(cam)
        cam.put_s(0x6dd,b'\x0a');cam.h.b.core.psw|=0x40
        cam.set_lock(-1 if timing=='race-at-s' else 0)
        state=dict(timing=timing,calls=[],stores=[],taken=False,armed=False,released=False)
        active['case']=state;calls=[]
        def service(b):
            if b.core.r[0]==6 and b.core.r[1] in (2,5,6):
                row=dict(op=b.core.r[1]);calls.append(row)
                R.SC.callback_return(cam,b,lambda q:row.update(result=C.c_int32(q.core.r[0]).value))
            return False
        cam.h.b.add_breakpoint(cam.symbol('rv_call'),service)
        before=R.N.snapshot(cam);before_summary=compact(cam);before_live=cam.engine_bytes(H.LAYOUT['g.live'],552)
        cam.press('DOWN');frame=cam.check_frame();after=R.N.snapshot(cam)
        for field in ('rows','T','S','ref'):assert after[field]==before[field],(target,timing,field)
        assert cam.engine_bytes(H.LAYOUT['g.live'],552)==before_live
        assert not state['stores'] and frame['cur']==target-1 and not frame['failed']
        assert [(x['op'],x['result']) for x in calls]==([(6,0),(2,-2)] if timing=='race-at-s' else [(6,-2)]),calls
        assert (after['W']>before['W']) if timing=='race-at-s' else (after['W']==before['W'])
        if timing=='race-at-s':assert state['taken']
        if timing=='transient':assert state['released'] and cam.lock()==(-1,55)
        refused=compact(cam)
        R.N.exit_menu(cam,'half' if timing=='race-at-s' else 'ok')
        closed=compact(cam);cam.open_menu();cam.check_frame();reopened=compact(cam)
        for sample in (R.N.snapshot(cam),):
            for field in ('rows','T','S','ref'):assert sample[field]==before[field]
        assert closed['unit_sha256']==before_summary['unit_sha256'] and closed['S_sha256']==before_summary['S_sha256']
        assert not state['stores']
        cases.append(dict(target=target,timing=timing,calls=calls,S_stores=state['stores'],
                          before=before_summary,refused=refused,closed=closed,reopened=reopened,
                          published=published,audit=R.V.audit(cam)))
        active['case']=None
    return dict(cases=cases)


def continuation(unit):
    sequence=R.N.load(R.ROOT/'research/review_g124/native_sequence.py','review154_sequence')
    cases=[]
    for kind in ('keep1','part1'):
        cam=Camera(unit);R.CC.seed(cam,5,5,5);cam.open_menu();cam.select_effect(1)
        if R.N.CONTROL:
            cam.goto(0);cam.press('DISP')
        assert cam.ui('screen')==0 and cam.ui('cur')==8
        if kind=='part1':
            sequence.prepare_input(cam.h);sequence.device_edges(cam.h,cam.p)
        entries=[];settings_stores=[]
        for name in ('ig_menu','ig_event','ig_apply','ig_panel_open','ig_panel_event'):
            cam.h.b.add_breakpoint(cam.symbol(name),lambda b,name=name:entries.append(name) or False)
        cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:settings_stores.append(dict(offset=e.address-cam.s,data=e.data.hex(),origin=e.origin)))
        baseline=R.N.snapshot(cam);base_live=cam.engine_bytes(H.LAYOUT['g.live'],552)
        frames=[dict(step='before',sample=compact(cam),entries=list(entries),parent_tag=cam.h.u(0x2037f3bc))]
        if kind=='keep1':
            R.CC.set_keep(cam,1);cam.press('OK')
        else:
            sequence.key(cam.h,cam.m.fr,0x0d)
            hidden=R.N.snapshot(cam)
            for field in ('rows','T','S','W'):assert hidden[field]==baseline[field],('hidden',field)
            for address in (0x201c06f4,0x201c092c):
                done=cam.m.fr.native(cam.h,address,(1,0,0),steps=30000000);assert done['ok']
            done=cam.m.fr.native(cam.h,0x20287080,(),steps=30000000);assert done['ok']
        frames.append(dict(step=kind,sample=compact(cam),entries=list(entries),parent_tag=cam.h.u(0x2037f3bc)))
        for key in ('DOWN','UP','DISP','OK','ADJ'):
            if key in ('OK','ADJ'):R.CC.set_keep(cam,0)
            cam.press(key)
            sample=R.N.snapshot(cam)
            frames.append(dict(step=key,sample=compact(cam),entries=list(entries),parent_tag=cam.h.u(0x2037f3bc)))
            for field in ('rows','T','S','W'):assert sample[field]==baseline[field],(kind,key,field)
            assert cam.engine_bytes(H.LAYOUT['g.live'],552)==base_live,(kind,key,'live')
            assert cam.h.u(0x2022f5ac,1) in (7,8)
        assert not settings_stores,settings_stores
        mismatches=[x['step'] for x in frames if x['sample']['native']['rows']==8 and
                    x['sample']['frame']['native_cursor']!=x['sample']['frame']['physical']+1]
        no_navigation=kind=='keep1' and 'ig_apply' not in entries
        cases.append(dict(kind=kind,observation='OPEN' if mismatches or no_navigation else 'ALIGNED',mismatch_steps=mismatches,
                          no_DAT_navigation=no_navigation,
                          frames=frames,S_stores=settings_stores,unit_W=0,full_recipe_preserved=True))
    return dict(cases=cases)


def cap(unit):
    ref=R.REF.Reference(154);window_count=0
    for count in (1,8,9,19,22,49):
        for current in range(count):
            for prior in range(count):
                out=(C.c_uint8*2)(165,165)
                assert ref.lib.check_window(count,current,prior,out)==0
                assert out[0]+out[1]==current and out[1]<8 and out[0]<=max(0,count-8)
                window_count+=1
    for count,current,prior in ((0,0,0),(50,49,42),(49,49,0)):
        out=(C.c_uint8*2)(165,165)
        assert ref.lib.check_window(count,current,prior,out)==-1 and list(out)==[165,165]
    cases=[]
    specs=[(0,10,R.ROOT/'firmware/package_v39_g154/local/SD_ROOT/GXRCE.DAT'),
           (3,10,H.DAT)]+[(u,k,R.CAP.fixture(u,k)) for u,k in ((30,10),(31,10),(32,10),(32,8),(32,0),(0,0))]
    for users,looks,path in specs:
        cam=Camera(unit,dat=path);before=R.N.snapshot(cam);accept=users<=min(32,40-looks)
        cam.h.parent();opened=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert opened['ok']
        if not accept:
            assert R.CC.native(cam)['rows']==7
            after=R.N.snapshot(cam)
            for field in ('rows','T','S','W'):assert after[field]==before[field]
            cases.append(dict(users=users,looks=looks,result='REJECT',native=R.CC.native(cam),unit_W=0,S_equal=True))
            continue
        frame=cam.check_frame();assert frame['count']==9+looks+users
        publications=observe_rows(cam);frames=[frame]
        for row in sorted(set((0,7,8,7+looks,8+looks,frame['count']-2,frame['count']-1))):
            if 0<=row<frame['count']:
                cam.goto(row);frames.append(cam.check_frame())
                if users and row==frame['count']-2:
                    raw=path.read_bytes();slot,levels,name=R.REF.user_record(raw,users)
                    status,entry=ref.compute(raw,H.UNITS[unit],expand(raw,H.UNITS[unit],slot),levels)
                    assert status==0 and cam.ui('applied_user')==users
                    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry and cam.unit_rows()==R.N.expected(cam,entry)
                    assert frames[-1]['labels'][frames[-1]['physical']][1:]==name
        cam.press('DOWN');assert cam.check_frame()['cur']==0
        cam.press('UP');assert cam.check_frame()['cur']==frame['count']-1
        assert publications and all(len(t)<=13 for f in frames for t in f['labels'])
        cases.append(dict(users=users,looks=looks,result='ACCEPT',logical_rows=frame['count'],frames=frames,
                          publications=publications,dat_sha256=R.digest(path.read_bytes())))
    tool=R.N.load(R.ROOT/'firmware/engine_v63_g154/candidate/user_entries.py','review154_user_tool')
    tools=[]
    for masks,counts,limit in (([7]*2+[6]*6+[2]*2,[2,10,8],30),([1]*2+[2]*8,[2,8,0],32)):
        raw=bytearray(R.CAP.fixture(32,10).read_bytes());area,length=effect_area(raw)
        for i,mask in enumerate(masks):
            raw[area+32+32*i+18]=mask
            struct.pack_into('>I',raw,area+32+32*i+4,content_crc(expand_effect(raw,i),mask))
        struct.pack_into('>I',raw,area+24,crc(raw[area+32:area+length]));struct.pack_into('>I',raw,area+28,crc(raw[area:area+28]));raw=seal(raw)
        assert strict_effects(raw)['count']==10
        actual=[sum(bool(mask&(1<<m)) for mask in masks) for m in range(3)]
        assert actual==counts and tool.entry_limit(raw)==limit
        try:parsed=tool.parse(raw);accepted=True
        except ValueError:accepted=False
        assert accepted==(32<=limit)
        tools.append(dict(visible=actual,global_limit=limit,users=32,tool_accepted=accepted))
    return dict(window_cases=window_count,cases=cases,asymmetric_tool=tools)


def cards(unit):
    return R.V.cards(unit)


def navigation(unit):
    cam=Camera(unit);cam.open_menu();ref=R.REF.Reference(154);publications=observe_rows(cam);cases=[]
    for row in (8,17,18,19,20,21,0):
        cam.goto(row);frame=cam.check_frame();entry=R.V.wanted(cam,row,ref)
        assert frame['screen']==0 and frame['cur']==row and frame['count']==22
        assert all(text.strip() not in ('Looks','MyRec') for text in frame['labels'])
        if entry is not None:
            assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
            assert cam.unit_rows()==R.N.expected(cam,entry)
        cases.append(dict(row=row,frame=frame,entry_sha256=R.digest(entry) if entry else None))
    return dict(cases=cases,publications=publications,audit=R.V.audit(cam))


def cache(unit):
    trace=[]
    def observed_camera(*args,**kwargs):
        cam=Camera(*args,**kwargs)
        def store(event):
            base=getattr(cam.p,'image_base',0)
            raw=H.DAT_BYTES[cam.dat_path]
            if base and event.pc and base+u32(raw,132)<=event.pc<base+u32(raw,132)+u32(raw,136):
                state=cam.h.u(0x205a293c);own=cam.h.u(cam.adapter+H.LAYOUT['list']+12)
                psw=cam.h.b.core.psw
                assert not psw&0x40,(hex(event.pc),hex(psw))
                assert state in (0x2022f71c,own),(hex(state),hex(own))
                assert cam.h.u(0x205d9bf8)==8 and cam.h.u(0x205d9c00)==56
                trace.append(dict(value=event.data[0],pc=hex(event.pc),psw=psw,state=hex(state),own_snapshot=hex(own)))
        cam.h.b.add_write_trace(0x205a2944,0x205a2945,store)
        return cam
    original=R.CC.Camera;R.CC.Camera=observed_camera
    try:
        cases=[R.CC.error_close(unit,0,False),R.CC.error_close(unit,1,True),
               R.CC.ordinary(unit,'last_user_close',5,5,5,target=20),
               R.CC.ordinary(unit,'last_user_keep1_DAT_then_close',5,5,5,target=20,keep1=True)]
    finally:R.CC.Camera=original
    assert trace
    return dict(cases=cases,DAT_cache_stores=trace,all_DAT_cache_stores_inside_IRQ=True)


def cross(unit):
    import shutil
    result=R.ST.cross(unit)
    source=R.TMP/('cross-control' if R.N.CONTROL else 'cross')/'runtime/evidence'
    target=R.OUT/'evidence'/('cross-'+unit);target.mkdir(exist_ok=True)
    copied=[]
    for path in source.glob('*'):
        if path.is_file():
            shutil.copyfile(path,target/path.name)
            copied.append(dict(path=str((target/path.name).relative_to(R.OUT)),sha256=R.digest(path.read_bytes())))
    result['copied_evidence']=copied
    return result


def identity(unit):
    current=dict(body=R.ROOT/'firmware/package_v39_g153/local/SD_ROOT/ilaunch3',resident=R.ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf')
    old=dict(body=R.ROOT/'firmware/package_v39_g151/local/SD_ROOT/ilaunch3',resident=R.ROOT/'firmware/resident_v39/local/resident/build/resident.elf')
    v38=dict(body=R.ROOT/'firmware/package_v38_g152/local/SD_ROOT/ilaunch3',resident=R.ROOT/'firmware/resident_v38/local/resident/build/resident.elf')
    new=H.DAT;g153=R.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT';g151=R.ROOT/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT'
    specs=[('new-current',current,new,154,True),('g153-current',current,g153,153,True),
           ('g151-current',current,g151,154,False),('new-g151',old,new,151,False),
           ('g153-g151',old,g153,151,False),('new-v38',v38,new,139,False)]
    cases=[]
    for name,body,dat,generation,accept in specs:
        H.BODY=body['body'];H.BODY_SHA=R.digest(H.BODY.read_bytes());H.RESIDENT=body['resident']
        tree={154:'engine_v63_g154',153:'engine_v62_g153',151:'engine_v59_g151',139:'engine_v56_g139'}[generation]
        H.ENGINE=R.ROOT/('firmware/'+tree+'/candidate/local/full-r13/engine.elf')
        model_dat=dat if accept else new if generation==154 else g151 if generation==151 else R.ROOT/'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT'
        cam=Camera(unit,dat=model_dat);cam.p.files.paths['/ATA1/GXRCE.DAT']=dat.read_bytes();calls=[]
        cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'],lambda b:calls.append(True) or False)
        before=R.N.snapshot(cam);cam.h.parent();done=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert done['ok']
        rows=cam.h.u(0x2022f5ac,1);after=R.N.snapshot(cam)
        assert rows==(8 if accept else 7)
        assert bool(calls)==accept
        if not accept:assert not calls and cam.h.u(H.R+148)==0
        for field in ('rows','T','S','W'):assert after[field]==before[field],(name,field)
        cases.append(dict(name=name,accepted=accept,rows=rows,DAT_entries=len(calls),S_equal=True,unit_W=0,
                          body_sha256=H.BODY_SHA,dat_sha256=R.digest(dat.read_bytes())))
    return dict(cases=cases)


def static(unit):
    old=R.ROOT/'firmware/engine_v62_g153';new=R.ROOT/'firmware/engine_v63_g154'
    def sources(base):
        return {str(p.relative_to(base)):R.digest(p.read_bytes()) for p in base.rglob('*')
                if p.is_file() and 'local' not in p.relative_to(base).parts and p.suffix in ('.c','.h','.S','.ld','.py')}
    a,b=sources(old),sources(new)
    differences=[name for name in a.keys()|b.keys() if a.get(name)!=b.get(name)]
    frozen=[name for name in a if name.startswith(('resident/','candidate/engine_services/'))]
    assert frozen and all(a[name]==b[name] for name in frozen)
    core='candidate/containers/product/src/firmware/engine/core/eng_core.c'
    assert a[core]==b[core]=='c62ca5337493c3ce974a30e8e7ca4b8bc68d593a0b965d1600dcc0fdeee7482d'
    bodies=[]
    base=R.ROOT/'firmware/package_v39_g153/local/SD_ROOT'
    for package in ('package_v39_g154','package_v39_g154_test'):
        folder=R.ROOT/'firmware'/package/'local/SD_ROOT'
        names=[p.name for p in folder.iterdir() if p.is_file() and p.name!='GXRCE.DAT']
        assert len(names)==29
        assert all((folder/name).read_bytes()==(base/name).read_bytes() for name in names)
        bodies.append(dict(package=package,identical_files=len(names),body_sha256=R.digest((folder/'ilaunch3').read_bytes())))
    raw=(R.ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    release=(R.ROOT/'firmware/package_v39_g154/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert R.digest(raw)=='ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e'
    assert R.digest(release)=='3c63ae08a1387af9aa5c7d30107a17e37ec743b592c6f8833e70374e8b760449'
    assert bodies[0]['body_sha256']=='8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
    assert raw[48:112]==(R.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()[48:112]
    section=u32(raw,204);old_raw=(R.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert raw[section+3392:section+11296]==old_raw[u32(old_raw,204)+3392:u32(old_raw,204)+11296]
    adapter=(new/'candidate/containers/product/adapter.c').read_text()
    assert all(token not in adapter for token in ('UV_GROUP','UV_ENTRIES','UV_LOOKS','uv_group_entry','uv_count_group'))
    retained={name:adapter.count('n.ui.'+name) for name in ('group','origin','entry_cur','look_cur')}
    elf=(new/'candidate/local/full-r13/engine.elf').read_bytes()
    table=u32(elf,32);entry_size=int.from_bytes(elf[46:48],'big');number=int.from_bytes(elf[48:50],'big');strings=int.from_bytes(elf[50:52],'big')
    string_header=table+entry_size*strings;names=elf[u32(elf,string_header+16):u32(elf,string_header+16)+u32(elf,string_header+20)]
    sections=[];code=raw[u32(raw,132):u32(raw,132)+u32(raw,136)]
    for i in range(number):
        at=table+entry_size*i;name=names[u32(elf,at):].split(b'\0')[0].decode();offset,size=u32(elf,at+16),u32(elf,at+20)
        sections.append(dict(name=name,size=size,offset=offset,code_equal=(elf[offset:offset+size]==code and size==len(code))))
    assert any(x['code_equal'] for x in sections),sections
    bss=sum(x['size'] for x in sections if x['name']=='.bss')
    main_bytes=7628+((len(raw)+bss+3)&~3)
    assert main_bytes<=107612 and len(raw)<=98304 and len(code)<=65536
    return dict(source_files=[len(a),len(b)],differences=sorted(differences),frozen_resident_services=len(frozen),core_sha256=a[core],
                packages=bodies,test_sha256=R.digest(raw),release_sha256=R.digest(release),R3_identical=True,
                removed_fields_accesses=retained,elf_sections=sections,code_bytes=len(code),DAT_bytes=len(raw),BSS_bytes=bss,main_bytes=main_bytes)
