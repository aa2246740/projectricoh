"""Drive the real body/resident/DAT machine code with task-local host fixtures."""
import argparse, json, os, struct, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *
import bytes_review as B
guard()
os.environ.setdefault('GXR_HARNESS_BACKEND','c')
sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
import python_backend
python_backend.CACHE=TMP/'decode'
import harness, field_replay, product_execute, engine_bridge
H=load(ROOT/'research/v39_g153/tests/v39_host.py','review_looks18_host')
H.LOCAL=TMP/'native'/('p'+str(os.getpid()));H.TMP=H.LOCAL/'tmp'
BASELINE=os.environ.get('REVIEW_DAT')=='baseline'
H.PACKAGE=(BASE_PACKAGE if BASELINE else PACKAGE)/'local/SD_ROOT';H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
H.ENGINE=TMP/'link'/('control' if BASELINE else 'final')/'engine.elf'
H.RESIDENT=ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf'
H.LAYOUT=json.loads((ROOT/'research/g154_looks_r1/layout.json').read_text());H.UI=H.LAYOUT['ui']
H.setup()
assert Path(python_backend.__file__).parent==ROOT/'tools/native_harness_c'
if os.environ['GXR_HARNESS_BACKEND']=='c':assert python_backend.PythonBackend.native_api==5

class Camera(H.Camera):
    def symbol(self,name):
        if name not in self.p.elf.symbols:
            found=[x for x in self.p.elf.symbols if x.startswith(name+'.')];assert len(found)==1
            name=found[0]
        return self.p.symbol_pc(name)
    def state(self):
        d=super().state();d['effect']=self.ui('effect');return d

def published(cam):
    values=[]
    def call(b):
        if b.core.r[0]==10 and b.core.r[1] in (1,3):
            pointer=cam.h.u(b.core.r[2]+48);count=cam.h.u(pointer+20)
            values.append(count);assert count==8,('physical rows',count)
        return False
    attached=[]
    def attach(b):
        if not attached:
            address=cam.symbol('rv_call');cam.h.b.add_breakpoint(address,call);attached.append(address)
        return False
    if cam.p.image_base:attach(None)
    else:cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'],attach)
    return values

def observed(cam,entry):
    assert len(entry)==552
    assert cam.engine_bytes(H.LAYOUT['g.live'],552)==entry
    expected=([entry[o:o+n] for o,n,_ in B.CRCS],B.U16(entry,445))
    assert cam.unit_rows()==expected

def frame(cam):
    st=cam.check_frame()
    assert all(len(x)<=13 for x in st['labels'])
    assert len(st['labels'])==8
    return st

def navigation(unit):
    cam=Camera(unit);rows=published(cam);alloc=[]
    cam.h.b.add_breakpoint(cam.h.symbols['rv_native_alloc'],lambda b:alloc.append(b.get_reg('r0')) or False)
    cam.open_menu();math=B.HostMath();raw=dat();u=H.UNITS[unit]
    root=H.R;block=cam.h.u(root+56);image=cam.h.u(block+312)
    sizes=dict(main_request=cam.h.u(root+104),code_bytes=cam.h.u(root+116),file_bytes=cam.h.u(block+316),bss_bytes=cam.h.u(block+320),
               allocation_requests=alloc,block=block,image=image,image_offset=image-block,allocation_span=cam.h.u(block-4))
    assert sizes['main_request']==103644 and 103644 in alloc
    assert sizes['image_offset']==1228 and sizes['code_bytes']==64728 and sizes['file_bytes']==86736 and sizes['bss_bytes']==9280
    assert image+86736+9280<=block+103644
    records=[]
    for row in list(range(30))+list(range(28,-1,-1)):
        cam.goto(row);f=frame(cam);assert f['screen']==0 and f['cur']==row and f['count']==30
        entry=B.expected(raw,u,row,math,cam.levels())
        if entry is not None:observed(cam,entry)
        label=f['labels'][f['physical']]
        if 8<=row<26:assert label[1:]==B.look_descriptor(raw,row-8)[20:].rstrip(b'\0').decode()
        if 26<=row<29:assert label[1:]==B.user(raw,row-26)[2]
        if row==29:assert label==' DISP:Tw'
        records.append(dict(frame=f,live_552_sha256=sha(entry) if entry else None))
    cam.goto(29);cam.press('DOWN');assert frame(cam)['cur']==0
    cam.press('UP');assert frame(cam)['cur']==29
    assert rows and set(rows)=={8}
    return dict(records=records,published_rows=rows,sizes=sizes,wrap_both=True)

def cards(unit):
    cam=Camera(unit);rows=published(cam);cam.open_menu();math=B.HostMath();raw=dat();u=H.UNITS[unit];records=[]
    for row in (2,*range(8,26),26):
        cam.goto(row);start=frame(cam);before=B.expected(raw,u,row,math,cam.levels());observed(cam,before)
        cam.press('DISP');card=frame(cam);assert card['screen']==1
        cam.goto(1);cam.press('DISP');f=frame(cam);assert f['screen'] in (2,3)
        if f['screen']==2:cam.press('DISP')
        assert frame(cam)['screen']==3
        cam.press('UP');changed=frame(cam);after=B.expected(raw,u,row,math,cam.levels());observed(cam,after)
        cam.press('DISP')
        if cam.ui('screen')==2:cam.goto(0);cam.press('DISP')
        assert frame(cam)['screen']==1
        cam.goto(0);cam.press('DISP');back=frame(cam)
        assert back['screen']==0 and back['cur']==row and '*' in back['labels'][back['physical']]
        records.append(dict(row=row,start=start,card=card,changed=changed,back=back,before_552_sha256=sha(before),after_552_sha256=sha(after)))
    assert rows and set(rows)=={8}
    return dict(cases=records,published_rows=rows)

def reseal(data):
    data=bytearray(data);struct.pack_into('>I',data,24,B.crc(data[256:]));data[20:24]=bytes(4)
    struct.pack_into('>I',data,20,B.crc(data[:256]));return bytes(data)

def capacity_fixture(count):
    raw=dat();tool=load(ENGINE/'candidate/user_entries.py','review_looks18_users')
    assert tool.entry_limit(raw)==22
    users=[dict(base=1,levels=[1]+[0]*10) for _ in range(count)]
    at=B.U32(raw,204)+1408
    if count<=22:
        out=tool.replace(raw,users);assert len(tool.parse(out)[2])==count
    else:
        for op in ('replace','parse'):
            bad=bytearray(raw);bad[at:at+1984]=tool.gxui.extension(raw[at+64:at+1216],tool.banks(raw),users);bad=reseal(bad)
            try:tool.replace(raw,users) if op=='replace' else tool.parse(bad)
            except ValueError as e:assert 'flat list user limit: 22' in str(e)
            else:raise AssertionError(('CLI accepted',count,op))
        out=bad
    folder=TMP/'fixtures';folder.mkdir(parents=True,exist_ok=True);path=folder/f'users-{count}.DAT';path.write_bytes(out)
    return path

def cap(unit):
    records=[];math=B.HostMath()
    for count in (22,23,32):
        path=capacity_fixture(count);raw=path.read_bytes();cam=Camera(unit,dat=path)
        before=(cam.s_bytes(0,4096),cam.unit_rows(),cam.writes())
        if count>22:
            cam.h.parent();r=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert r['ok']
            assert cam.h.u(0x2022f5ac,1)==7
            assert (cam.s_bytes(0,4096),cam.unit_rows(),cam.writes())==before
            records.append(dict(users=count,result='REJECT',physical_rows=7,unit_writes=0,settings_equal=True))
        else:
            rows=published(cam);cam.open_menu();assert frame(cam)['count']==49
            frames=[]
            for row in (26,47,48):
                cam.goto(row);f=frame(cam);assert f['cur']==row;frames.append(f)
                if row!=48:observed(cam,B.expected(raw,H.UNITS[unit],row,math,cam.levels()))
            cam.press('DOWN');assert frame(cam)['cur']==0
            cam.press('UP');assert frame(cam)['cur']==48
            assert rows and set(rows)=={8}
            records.append(dict(users=count,result='ACCEPT',logical_rows=49,published_rows=rows,frames=frames))
    return dict(cases=records)

def observer_probe(unit):
    cam=Camera(unit);bad_address=cam.symbol('rv_call');hits=[]
    cam.h.b.add_breakpoint(bad_address,lambda b:hits.append(b.pc) or False)
    cam.open_menu();good_address=cam.symbol('rv_call');f=frame(cam)
    assert bad_address!=good_address and not hits
    return dict(reproduced='Observer attached before DAT image base was published',old_address=bad_address,actual_address=good_address,wrong_observer_hits=hits,frame=f,firmware_frame_valid=True)

def set_keep(cam,value):
    r=cam.m.fr.native(cam.h,0x20265818,(value,));assert r['ok'] and cam.h.u(0x2037f2fe,1)==value

def continuation(unit):
    sequence=load(ROOT/'research/review_g124/native_sequence.py','review_looks18_sequence')
    cases=[]
    for kind in ('keep1','part1'):
        cam=Camera(unit);cam.h.b.origin='model:stock_cursor'
        for address in (0x2022f725,0x2022f726,0x205a2944):cam.h.b.write(address,bytes([5]))
        cam.h.b.origin='cpu';cam.open_menu();cam.goto(8);frame(cam)
        if kind=='part1':sequence.prepare_input(cam.h);sequence.device_edges(cam.h,cam.p)
        entries=[];stores=[]
        for name in ('ig_menu','ig_event','ig_apply','ig_panel_open','ig_panel_event'):
            cam.h.b.add_breakpoint(cam.symbol(name),lambda b,name=name:entries.append(name) or False)
        cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:stores.append(dict(offset=e.address-cam.s,data=e.data.hex(),origin=e.origin)))
        baseline=(cam.s_bytes(0,4096),cam.unit_rows(),cam.writes(),cam.engine_bytes(H.LAYOUT['g.live'],552))
        observations=[]
        def record(step):
            current=(cam.s_bytes(0,4096),cam.unit_rows(),cam.writes(),cam.engine_bytes(H.LAYOUT['g.live'],552))
            assert current==baseline,(kind,step,'recipe or settings changed')
            f=cam.state();observations.append(dict(step=step,frame=f,entries=list(entries),parent_tag=cam.h.u(0x2037f3bc),
                S_sha256=sha(current[0]),unit_sha256=sha(b''.join(current[1][0])+current[1][1].to_bytes(2,'big')),unit_writes=0,live_552_sha256=sha(current[3])))
        record('before')
        if kind=='keep1':set_keep(cam,1);cam.press('OK')
        else:
            sequence.key(cam.h,cam.m.fr,0x0d)
            assert (cam.s_bytes(0,4096),cam.unit_rows(),cam.writes(),cam.engine_bytes(H.LAYOUT['g.live'],552))==baseline
            for address in (0x201c06f4,0x201c092c):
                r=cam.m.fr.native(cam.h,address,(1,0,0),steps=30000000);assert r['ok']
            r=cam.m.fr.native(cam.h,0x20287080,(),steps=30000000);assert r['ok']
        record(kind)
        for key in ('DOWN','UP','DISP','OK','ADJ'):
            if key in ('OK','ADJ'):set_keep(cam,0)
            cam.press(key);record(key)
        assert not stores
        mismatches=[o['step'] for o in observations if o['frame']['rows']==8 and o['frame']['native_cursor']!=o['frame']['physical']+1]
        no_navigation=kind=='keep1' and 'ig_apply' not in entries
        cases.append(dict(kind=kind,behavior='OPEN' if mismatches or no_navigation else 'ALIGNED',mismatch_steps=mismatches,
                          no_DAT_navigation=no_navigation,observations=observations,S_stores=stores,unit_writes=0))
    return dict(cases=cases)

def rollback(unit):
    # Cold-boot model: carry the actual complete S bytes produced by the new
    # image into a fresh process-independent camera model loading baseline DAT.
    assert not BASELINE
    math=B.HostMath();raw=dat();oldraw=dat(True);records=[]
    for target in (18,25):
        cam=Camera(unit);cam.open_menu();cam.goto(target);observed(cam,B.expected(raw,H.UNITS[unit],target,math,cam.levels()))
        set_keep(cam,0);cam.press('OK');settings=cam.s_bytes(0,4096)
        saved_package,saved_dat,saved_engine=H.PACKAGE,H.DAT,H.ENGINE
        try:
            H.PACKAGE=BASE_PACKAGE/'local/SD_ROOT';H.DAT=H.PACKAGE/'GXRCE.DAT';H.ENGINE=TMP/'link/control/engine.elf'
            restored=Camera(unit);restored.put_s(0,settings);rows=published(restored);restored.open_menu();first=frame(restored)
            assert first['count']==22
            for row in (8,17,18,20,21):
                restored.goto(row);f=frame(restored)
                if row!=21:observed(restored,B.expected(oldraw,H.UNITS[unit],row,math,restored.levels()))
            assert rows and set(rows)=={8}
            records.append(dict(selected_new_row=target,saved_settings_sha256=sha(settings),baseline_dat_sha256=sha(oldraw),
                                first_frame=first,last_frame=f,published_rows=rows,scope='Fresh body/resident host model with persisted S; no physical card or power cycle'))
        finally:H.PACKAGE,H.DAT,H.ENGINE=saved_package,saved_dat,saved_engine
    return dict(cases=records)

def identity(unit):
    rows=[];saved=(H.BODY,H.BODY_SHA,H.RESIDENT,H.ENGINE)
    cases=[('current',H.BODY,H.RESIDENT,H.ENGINE,H.DAT,True),
           ('previous-v39',ROOT/'firmware/package_v39_g151/local/SD_ROOT/ilaunch3',ROOT/'firmware/resident_v39/local/resident/build/resident.elf',
            ROOT/'firmware/engine_v59_g151/candidate/local/full-r13/engine.elf',ROOT/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT',False),
           ('previous-v38',ROOT/'firmware/package_v38_g152/local/SD_ROOT/ilaunch3',ROOT/'firmware/resident_v38/local/resident/build/resident.elf',
            ROOT/'firmware/engine_v56_g139/candidate/local/full-r13/engine.elf',ROOT/'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT',False)]
    try:
        for name,body,resident,engine,model_dat,accept in cases:
            H.BODY=body;H.BODY_SHA=sha(body.read_bytes());H.RESIDENT=resident;H.ENGINE=engine
            cam=Camera(unit,dat=model_dat);cam.p.files.paths['/ATA1/GXRCE.DAT']=dat();entries=[]
            cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'],lambda b:entries.append(b.pc) or False)
            before=(cam.s_bytes(0,4096),cam.unit_rows(),cam.writes())
            cam.h.parent();opened=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert opened['ok']
            count=cam.h.u(0x2022f5ac,1);state=cam.h.u(H.R+5,1)
            assert (count,state)==((8,3) if accept else (7,6))
            assert bool(entries)==accept
            assert (cam.s_bytes(0,4096),cam.unit_rows(),cam.writes())==before
            if accept:assert cam.ui('count')==30
            rows.append(dict(case=name,body_sha256=H.BODY_SHA,dat_sha256=sha(dat()),result='ACCEPT' if accept else 'REJECT',
                             physical_rows=count,resident_state=state,DAT_entries=len(entries),settings_equal=True,unit_writes=0))
    finally:H.BODY,H.BODY_SHA,H.RESIDENT,H.ENGINE=saved
    return dict(cases=rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=('navigation','cards','cap','observer_probe','continuation','rollback','identity'));parser.add_argument('--unit',choices=H.UNITS,default='50mm');args=parser.parse_args()
    started=time.monotonic();detail=globals()[args.group](args.unit)
    result=dict(status='PASS',group=args.group,unit=args.unit,backend=os.environ['GXR_HARNESS_BACKEND'],dat_sha256=sha(H.DAT.read_bytes()),
                engine_elf_sha256=sha(H.ENGINE.read_bytes()),details=detail,seconds=time.monotonic()-started)
    suffix='-baseline' if BASELINE else ''
    save(f'evidence/{args.group}-{args.unit}-{os.environ["GXR_HARNESS_BACKEND"]}{suffix}.json',result)
    print(json.dumps({k:result[k] for k in ('status','group','unit','backend','seconds')}),flush=True)

if __name__=='__main__':main()
