"""Three-unit functional checks, complete callback counts and raw record checks."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import time
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as h
import gate as gate


def native_state(cam):
    return {hex(a):cam.h.u(a,w) for a,w in ((0x2022f5a8,4),(0x2022f5ac,1),(0x2022f725,1),(0x2022f726,1),(0x205a2944,1))}

def at(cam,typ,field):return cam.aux()+cam.off[typ+'.'+field]

def snapshot(cam):
    return cam.h.b.read(cam.record(),cam.off['record_size'])+cam.h.b.read(cam.aux(),cam.off['aux_size'])

def site(cam,address,resume,regs):
    b=cam.h.b;sp=b.get_reg('r15')
    for k,value in regs.items():b.set_reg(k,value&0xffffffff)
    def run():
        stop=b.call(address,(),resume,30000000)
        return dict(ok=stop.reason=='return',stop=stop.reason,pc=hex(stop.pc))
    result=cam.measured('site '+hex(address),run)
    b.set_reg('r15',sp)
    return result

def h10(cam,code):
    site(cam,0x202b120c,0x202b1210,{'r11':code})
    assert cam.h.b.get_reg('r11')==code

def prepare_regions(cam):
    b=cam.h.b
    b.map(0x20744800,bytes(0x177800))
    b.map(0x8733c000,bytes(262144))
    cam.fixture.append('controlled OSD and ER read fixtures, not camera observations')
    cam.configuring=True
    cam.h.put(0x200c0dc8,0x20744800)
    cam.h.put(0x200c0dd0,0x808bc000);cam.h.put(0x200c0dd4,0x076c0000)
    cam.h.put(0x205a1594,1,1)
    for i in range(5):cam.h.put(0x205a1998+4*i,0x20744a80+0x4b000*i)
    cam.configuring=False


def finish_bounds(cam,report):
    report['callback_max']=max(x['instructions'] for x in cam.callbacks)
    report['callbacks_over_limit']=[x for x in cam.callbacks if x['instructions']>2000000]
    report['g0_instruction_pass']=not report['callbacks_over_limit']
    report['model_stack_bytes']=0x206ffff0-min(int(x['min_sp'],16) for x in cam.callbacks)
    report['audit']=cam.audit()


def run(unit):
    start=time.monotonic();cam=h.Session(unit,True);prepare_regions(cam);report=dict(unit=unit,dat_sha256=s.sha(h.DAT),cases=[])
    print(unit,'started',flush=True)
    # The loader is part of H01 and is counted. Its known G0 failure stays visible.
    original=cam.h.u(0x2022f726,1)
    cam.open();assert cam.h.u(0x2022f5ac,1)==8
    report['initial_page']=cam.rows()
    for i in range(9):cam.move()
    allocation=cam.record()+cam.off['DgRecord.allocation']
    words=struct.unpack('>8I',cam.h.b.read(allocation,32));assert words[1]==7628+words[4]+words[5]
    assert words[3]+words[4]<=words[7]<words[7]+65536<=words[3]+words[4]+words[5]
    assert cam.h.b.read(cam.record()+cam.off['DgRecord.dat_header'],256)==h.DAT.read_bytes()[:256]
    current=cam.h.b.read(cam.aux(),768);meta=struct.unpack('>32I',current[:128])
    assert meta[0]==10 and meta[1]==1023 and meta[2]==1,meta
    assert meta[31]==0
    # Full unit bytes are checked independently against the connected unit's own image.
    expected=b''
    for i,size in enumerate(gate.SIZES):
        if i==9:expected+=cam.t0.to_bytes(2,'big');continue
        expected+=cam.p.unit_image.bytes_at(gate.ADDRESSES[unit][i],size)
    assert current[128:633]==expected
    assert current[633:640]==bytes(7)
    cam.disp();assert cam.u('stage')==3
    boot_pages=[]
    for index in range(37):
        boot_pages.append(cam.rows())
        if index<36:cam.move()
    cam.disp();assert cam.u('stage')==1
    report['boot_raw_pages']=boot_pages
    sealed_current=cam.h.b.read(cam.aux(),768)
    assert zlib.crc32(sealed_current[128:])&0xffffffff==cam.h.u(cam.aux()+124)
    report['cases'].append('complete current bytes and independent CRC');print(unit,'current complete',flush=True)
    cam.press(0x29)
    assert cam.h.u(0x2022f726,1)==original and cam.h.u(0x205a2944,1)==original
    # A real native state setter makes the test standby context explicit.
    assert cam.fr.native(cam.h,0x202b0a74,(5,)).get('ok')
    for code in (0x21,0x22,0x29):h10(cam,code)
    keys=cam.h.b.read(cam.record()+cam.off['DgRecord.keys'],4*cam.off['DgKey.size'])
    for i in range(4):
        assert int.from_bytes(keys[24*i:24*i+4],'big')>0
        assert int.from_bytes(keys[24*i+8:24*i+12],'big')==5
    report['cases'].append('H10 preserves Fn and standby half codes; close snapshot is state 5')
    cam.open();assert cam.h.u(0x205a2944,1)==original
    # Every normal named page has exactly eight complete text rows.
    pages={}
    for i in range(11):
        pages[str(cam.u('page'))]=cam.rows();cam.disp()
    assert set(pages)==set(map(str,range(11))),pages.keys()
    report['pages']=pages
    # Explicit scene selection is a declaration made by the operator.
    while cam.u('page')!=0:cam.disp()
    cam.move();assert cam.u('scene')==1
    assert cam.fr.native(cam.h,0x202b0a74,(5,)).get('ok')
    for _ in range(20):h10(cam,0x29)
    for i in range(5):
        base=cam.record()+cam.off['DgRecord.osd']+i*cam.off['DgLayer.size']
        assert cam.h.u(base+cam.off['DgLayer.pieces'],2)==4
        assert cam.h.u(base+cam.off['DgLayer.count'],2)==0
    report['cases'].append('all five OSD layers and twenty bounded pieces');print(unit,'OSD complete',flush=True)
    cam.open()
    # Record separate physical scans for JPEG and RAW. All 99 rows are read.
    while cam.u('page')!=0:cam.disp()
    while cam.u('scene')<5:cam.move()
    for index in (0,1):
        if index:cam.move()
        base=cam.aux()+cam.off['DgAux.slots']+index*cam.off['DgSlots.size']
        mask=[cam.h.u(base+cam.off['DgSlots.covered']+4*j) for j in range(4)]
        assert mask==[0xffffffff,0xffffffff,0xffffffff,7],mask
    report['cases'].append('both 99-item physical scans')
    # Continue the same boot through all three measurement kinds. Work is fixed.
    while cam.u('page')!=9:cam.disp()
    while cam.u('bw_kind')<3:
        cam.move(0x1f)
        if cam.u('bw_piece')%8==0:print(unit,'BW',cam.u('bw_kind'),cam.u('bw_piece'),flush=True)
    while cam.u('page')!=0:cam.disp()
    for kind in range(3):
        for index in range(32):
            base=cam.record()+cam.off['DgRecord.bw']+(32*kind+index)*24
            start_tick,end_tick,result,size,source,repeats,flags=struct.unpack('>5I2H',cam.h.b.read(base,24))
            assert size==(262144 if kind==0 else 65536) and repeats==(4 if kind==1 else 1)
            if kind==2:assert result==zlib.crc32(bytes(range(256))*256)&0xffffffff
    report['cases'].append('32 ER, 32 control and 32 CRC pieces')
    # Freeze preserves every raw byte while pages and subsequent body events run.
    while cam.u('scene')<10:cam.move()
    cam.move();assert cam.u('stage')==2
    raw=snapshot(cam);header=list(struct.unpack('>12I',raw[:48]));expected_crc=header[4]
    altered=bytearray(raw);altered[16:20]=bytes(4)
    assert zlib.crc32(altered)&0xffffffff==expected_crc
    assert header[3]==len(raw)
    (s.HERE/'evidence'/('record-'+unit+'.bin')).write_bytes(raw)
    for _ in range(4):cam.disp();cam.move()
    assert snapshot(cam)==raw and cam.h.b.read(cam.aux(),768)==sealed_current
    report['cases'].append('current and main freezes are immutable across navigation')
    cam.press(0x23)
    assert cam.h.u(0x2022f726,1)==original and cam.h.u(0x205a2944,1)==original
    for index,code in enumerate((0x23,0x2b,0x0d,0x29,0x63)):
        cam.open();cam.disp();cam.move();cam.press(code)
        assert cam.h.u(0x2022f5a8)==0x2022d610 and cam.h.u(0x2022f5ac,1)==7
        assert cam.h.u(0x2022f726,1)==original and cam.h.u(0x205a2944,1)==original
    report['cases'].append('five native close paths restore names, rows, cursor and cache')
    finish_bounds(cam,report);report['functional_status']='PASS';report['status']='PASS' if report['g0_instruction_pass'] else 'G0_FAILED'
    report['seconds']=round(time.monotonic()-start,2)
    s.save(s.HERE/'evidence'/('host-'+unit+'.json'),report)
    print(json.dumps(dict(unit=unit,status=report['status'],functional_status=report['functional_status'],
       callback_max=report['callback_max'],cases=len(report['cases']),seconds=report['seconds'])),flush=True)

if __name__=='__main__':
    s.enable()
    # Keep functional verification running while recording the separate instruction gate.
    original=h.Session.measured
    def measured(self,label,fn,limit=True):return original(self,label,fn,False)
    h.Session.measured=measured
    run(sys.argv[1])
