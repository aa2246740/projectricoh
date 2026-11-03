"""Header refusal, cursor restoration, partial snapshots and native body sites."""
from pathlib import Path
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H
import host_suite as F
import gate as G


def assert_ok(cam,result):
    assert result.get('ok'),result
    return result


def image_old(cam):
    reader=s.load(s.ROOT/'firmware/stage2l_switch/tools/build.py','diag_old_elf')
    elf=reader.Elf(s.ROOT/'firmware/resident_v38/local/resident/build/resident.elf')
    section=next(x for x in elf.sections if x['name']=='.resident')
    return elf,section,elf.content(section)


def header_cases(unit):
    cam=H.Session(unit,True);h=cam.h;p=cam.p;old_dat=s.ROOT/'firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT'
    # An actual load attempt on the new body refuses the old diagnostic before rv_invoke.
    p.files.paths={'/ATA1/GXRCE.DAT':old_dat.read_bytes()}
    before=h.b.visits[h.symbols['rv_invoke']];cam.open()
    assert h.b.visits[h.symbols['rv_invoke']]==before and h.u(0x2022f5ac,1)==7
    new_old=dict(invocations=0,root_state=h.u(H.R+5,1),old_dat_sha256=s.sha(old_dat))
    audit=cam.audit()
    # Execute the old resident's real pure header gate with its original trust bytes.
    old,section,blob=image_old(cam);saved=h.b.read(section['va'],len(blob))
    breakpoints={a:callback for a,callback in h.b.breakpoints.items() if 0x2005276c<=a<0x20054800}
    for a in breakpoints:h.b.breakpoints.pop(a,None)
    cam.configuring=True;h.b.write(section['va'],blob);cam.configuring=False
    q=cam.pe.SCRATCH;h.b.write(q,old_dat.read_bytes()[:256])
    positive=assert_ok(cam,p.call(old.symbols['rv_header']['value'],(q,len(old_dat.read_bytes()),old.symbols['rv_trust']['value'])))
    assert positive['r0']==0,positive
    h.b.write(q,H.DAT.read_bytes()[:256])
    value=assert_ok(cam,p.call(old.symbols['rv_header']['value'],(q,len(H.DAT.read_bytes()),old.symbols['rv_trust']['value'])))
    assert value['r0']!=0,value
    cam.configuring=True;h.b.write(section['va'],saved);cam.configuring=False
    for a,callback in breakpoints.items():h.b.add_breakpoint(a,callback)
    return dict(new_body_old_dat=new_old,old_body_old_dat_header=positive['r0'],old_body_new_dat=dict(status=value['r0'],old_resident_sha256=s.sha(s.ROOT/'firmware/resident_v38/local/resident/build/resident.elf')),audit=audit)


def cursor_cases(unit):
    cam=H.Session(unit,True);rows=[]
    for a,b,cache in ((7,3,1),(2,7,3),(1,1,6)):
        for code in (0x23,0x2b,0x0d,0x29,0x63):
            cam.h.parent();cam.configuring=True
            for address,value in ((0x2022f725,a),(0x2022f726,b),(0x205a2944,cache)):cam.h.put(address,value,1)
            cam.configuring=False
            cam.measured('cursor open',lambda:cam.fr.native(cam.h,0x20287080,steps=30000000),False)
            cam.move();cam.press(code)
            actual=(cam.h.u(0x2022f725,1),cam.h.u(0x2022f726,1),cam.h.u(0x205a2944,1))
            assert actual==(a,b,b),(a,b,code,actual)
            rows.append(dict(a=a,b=b,pre_cache=cache,key=code,restored=actual))
    # A text conversion error withdraws the owned list and restores the original cursor.
    cam.open();home=cam.u('home');cam.h.stub(0x201d73e0,'ascii_failure',value=-1)
    cam.move();assert cam.h.u(0x2022f5ac,1)==7 and cam.h.u(0x205a2944,1)==home
    return dict(exits=rows,text_failure='closed',audit=cam.audit())


def partial_cases(unit):
    bad=H.Session(unit,False);bad.open();count=len(bad.p.rpc.log);bad.move()
    assert count==len(bad.p.rpc.log)==0
    assert bad.h.u(bad.aux()+8)&4
    bad_audit=bad.audit()
    cam=H.Session(unit,True);cam.open();rpc=len(cam.p.rpc.log);psw=cam.h.b.get_reg('psw')
    cam.h.b.set_reg('psw',psw&~0x40);cam.move();cam.h.b.set_reg('psw',psw)
    assert len(cam.p.rpc.log)==rpc and cam.h.u(cam.aux()+8)&4
    irq=cam.audit()
    clock=H.Session(unit,True);clock.open();clock.h.stub(0x2005f164,'stopped_tick',value=9)
    for _ in range(9):clock.move()
    clock.disp();cur=clock.h.b.read(clock.aux(),768);meta=struct.unpack('>32I',cur[:128])
    ctx=dict(boot=meta[6],unit=unit,unit_epoch=meta[7],link_epoch=meta[29],s_epoch=meta[30],set=1,phase='P04_CURRENT')
    expanded=G.expand_current(cur.hex(),ctx)
    try:G.validate_current(expanded,cur.hex(),ctx,dict(boot=meta[6],unit=unit,unit_epoch=meta[7]))
    except G.g.InvalidRecord as error:reason=error.code
    else:raise AssertionError('stopped time accepted')
    return dict(bad_s=bad_audit,irq_disabled=irq,stopped_tick=dict(reason=reason,audit=clock.audit()))


def body_cases(unit):
    cam=H.Session(unit,True);F.prepare_regions(cam);cam.open()
    for _ in range(9):cam.move()
    cam.disp()
    for _ in range(36):cam.move()
    cam.disp()
    cam.move();assert cam.u('scene')==1
    front=0x20744a80;line=b''.join(bytes([i+1])*40 for i in range(16))
    cam.configuring=True;cam.h.b.write(front,line*480);cam.configuring=False
    cam.press(0x29);assert cam.fr.native(cam.h,0x202b0a74,(5,)).get('ok')
    begin=len(cam.callbacks)
    for _ in range(4):F.h10(cam,0x29)
    at=cam.record()+cam.off['DgRecord.osd'];layer=cam.h.b.read(at,cam.off['DgLayer.size'])
    rect=cam.off['DgLayer.rect'];rectangles=[struct.unpack('>4H2B',layer[rect+10*i:rect+10*i+10]) for i in range(16)]
    assert rectangles==[(40*i,0,40,480,i+1,0) for i in range(16)],rectangles
    worst_osd=[row['instructions'] for row in cam.callbacks[begin:]]
    cam.open()
    # Explicitly arm S06. Earlier scenes remain incomplete in this focused case.
    while cam.u('scene')<5:cam.move()
    K=0x205757a4;PARAM=0x20610000
    native_k=[]
    def trace(event):
        if not cam.configuring:
            native_k.append(dict(pc=hex(event.pc) if event.pc is not None else None,address=hex(event.address),bytes=len(event.data)))
    cam.h.b.add_write_trace(K,K+588,trace)
    parameter_writes=[]
    cam.h.b.add_write_trace(PARAM,PARAM+144,lambda event:parameter_writes.append((event.address,len(event.data))) if not cam.configuring else None)
    cam.configuring=True;cam.h.b.map(PARAM,bytes(range(144)))
    raw=bytearray(588);raw[:128]=bytes(range(128));struct.pack_into('>I',raw,0x14c,0x81000000)
    struct.pack_into('>3H',raw,0x154,8576,4288,2848);struct.pack_into('>I',raw,0x70,2)
    cam.h.b.write(K,raw);cam.configuring=False
    cam.h.stub(0x2016583c,'declared_encoder_result',value=0)
    cam.fixture.append('H09 block, K fields and encoder result are explicit device-boundary fixtures')
    F.site(cam,0x2017098c,0x20170990,{'r5':PARAM})
    assert not parameter_writes,parameter_writes
    before=cam.h.b.read(K,588);sp=cam.h.b.get_reg('r15')
    cam.h.put(sp+4,0x201558a8)
    F.site(cam,0x2015f9d8,0x2015f9dc,{'r8':K,'r0':0})
    assert cam.h.b.read(K,588)==before
    assert not native_k,native_k
    origin=cam.record()+cam.off['DgRecord.requests'];source=cam.h.b.read(origin,164)
    assert struct.unpack('>5I',source[:20])[4]==144 and source[20:]==bytes(range(144))
    at=cam.record()+cam.off['DgRecord.k_sources'];saved=cam.h.b.read(at,164)
    assert struct.unpack('>5I',saved[:20])[4]==128 and saved[20:148]==before[:128]
    cam.h.put(sp+4,0x2015eaa4);F.site(cam,0x2015f9d8,0x2015f9dc,{'r8':K,'r0':0})
    assert cam.h.b.read(K,588)==before and not native_k
    for caller in (0x20155428,0x20155478,0x2015e9b0):
        cam.h.put(sp+4,caller);F.site(cam,0x2015f9d8,0x2015f9dc,{'r8':K,'r0':0})
        assert cam.h.b.read(K,588)==before
    return dict(k_bytes_unchanged=True,h09_raw_bytes=144,h40_raw_bytes=128,unpaired=True,
                whitelist_k_writes=0,h09_parameter_writes=0,whitelist_callers=[hex(v) for v in (0x201558a8,0x2015eaa4)],
                other_callers_same_value_k_writes=native_k,
                sixteen_rectangles=rectangles,osd_callback_instructions=worst_osd,audit=cam.audit())


def main():
    s.enable();unit=sys.argv[1];case=sys.argv[2]
    cam_method=H.Session.measured
    H.Session.measured=lambda self,label,fn,limit=True:cam_method(self,label,fn,False)
    fn={'headers':header_cases,'cursors':cursor_cases,'partial':partial_cases,'body':body_cases}[case]
    result=fn(unit);s.save(s.HERE/'evidence'/('boundary-'+case+'-'+unit+'.json'),dict(status='PASS',unit=unit,dat_sha256=s.sha(H.DAT),result=result))
    print('PASS',case,unit)

if __name__=='__main__':main()
