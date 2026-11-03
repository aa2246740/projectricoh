"""Three-unit UI/current checks and the repaired burst closure, without claiming a full capture."""
from pathlib import Path
import struct,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import host as H
import host_suite as F
import factory,gate
from complete_model import photo,standby,menu

def run(unit):
    start=time.monotonic();c=H.Session(unit,True)
    c.h.stub(0x2005f164,'declared_quick_model_tick',lambda b:(5000000+c.ops//1000)&0xffffffff)
    c.fixture.append('focused current-read model clock: 1000 instructions per 1 ms tick, not a measured device rate')
    factory.prepare(c);home=c.h.u(0x2022f726,1)
    c.open();assert c.h.u(0x2022f5ac,1)==8
    for _ in range(9):c.move()
    expected=b''.join(c.p.unit_image.bytes_at(gate.ADDRESSES[unit][i],size) if i<9 else c.t0.to_bytes(2,'big') for i,size in enumerate(gate.SIZES))
    assert c.h.b.read(c.aux()+128,505)==expected
    c.disp();cur=c.h.b.read(c.aux(),768);m=struct.unpack_from('>32I',cur)
    ctx=dict(boot=m[6],unit=unit,unit_epoch=m[7],link_epoch=m[29],s_epoch=m[30],set=1,phase='P04_CURRENT')
    try:gate.validate_current(gate.expand_current(cur.hex(),ctx),cur.hex(),ctx,dict(boot=m[6],unit=unit,unit_epoch=m[7]))
    except gate.g.InvalidRecord:
        s.save(s.HERE/'evidence'/('current-rejected-'+unit+'.json'),dict(raw=cur.hex(),context=ctx));raise
    c.h.put(c.at('page')+4,36);c.disp();standby(c)
    for code in (0x21,0x22,0x29):F.h10(c,code)
    menu(c);pages={}
    for _ in range(11):pages[str(c.u('page'))]=c.rows();c.disp()
    assert set(pages)==set(map(str,range(11)))
    c.h.put(c.at('scene'),8)
    photos=[photo(c,i,True) for i in range(3)]
    a=c.record()+c.off['DgRecord.scene']+8*24
    assert c.h.u(a+12)>0 and c.h.u(a+20,2)==3 and c.h.u(a+22,2)==1
    menu(c);c.h.put(c.at('scene'),10);c.h.put(c.at('page'),0);c.move();assert c.u('stage')==2
    raw=F.snapshot(c);(s.HERE/'evidence'/('quick-record-'+unit+'.bin')).write_bytes(raw)
    for code in (0x23,0x2b,0x0d,0x29,0x63):
        if c.h.u(0x2022f5ac,1)!=8:c.open()
        c.press(code);assert c.h.u(0x2022f726,1)==home and c.h.u(0x205a2944,1)==home
    result=dict(status='PASS',functional_status='PASS',unit=unit,dat_sha256=c.dat_hash,pages=pages,photos=photos,
       complete_native_capture=False,current_rows=10,burst_closure=True,audit=c.audit(),seconds=round(time.monotonic()-start,2))
    s.save(s.HERE/'evidence'/('host-'+unit+'.json'),result);print('PASS current/pages/burst/exits',unit,flush=True)
if __name__=='__main__':s.enable();run(sys.argv[1])
