"""Run final DAT instructions with explicit native UI and unit models."""
from pathlib import Path
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from machine import Machine, MASK
from unit_replay import Unit

ROOT = HERE.parents[1]
L = json.loads((HERE/'layout.json').read_text())
DAT = (ROOT/'firmware/package_v38_probe_p1/SD_ROOT/GXRCE.DAT').read_bytes()
I = 0x20600000
R = 0x20054700


class Session:
    def __init__(self, name='jlaunch', version=0x151):
        self.m = m = Machine((HERE/'engine-elf.txt').read_text())
        m.relocate(I)
        self.s = I-L['RV_SESSION_BYTES']
        self.n = I+len(DAT)
        self.page = 0
        self.cursor = 0
        self.cells = {0x2012ebe0:0xffff,0x2012ebe2:0xffff,
                      0x12c03b06:0x8100,0x12c03b10:0x42,0x12c03b00:7}
        self.rpc_log = []
        self.writes = []
        self.rpc_case = None
        self.text_case = None
        self.ready = 1
        self.context_kind = 0
        self.ignore_w = False
        m.put(I,DAT)
        reloc_at = int.from_bytes(DAT[144:148],'big')
        patch,target=struct.unpack_from('>II',DAT,reloc_at)
        m.w(I+patch,I+target)
        self.block_size = L['RV_SESSION_BYTES']+((len(DAT)+1068+3)&~3)+6144+256
        self.rw('magic',0x52565333)
        for member,value in [('version',32),('state',3),('inflight',1)]:
            self.rw(member,value,1)
        for i in range(12): m.w(R+L['RvRoot.epoch']+4*i,1)
        for member,value in [('block',self.s),('inverse',~self.s),('lease',1),
          ('lease_inverse',~1),('boot_epoch',1),('heap_epoch',1),('next_token',1),
          ('heap_begin',0x20500000),('heap_end',0x20704800),
          ('block_bytes',self.block_size),('alloc_bytes',self.block_size+12),
          ('code_address',I+256),('code_bytes',11596)]:
            self.rw(member,value)
        m.w(0x200d3488,0x20500000);m.w(0x200d348c,0x20704800)
        m.w(0x200c0dc4,0x400000)
        m.w(self.s-12,0);m.w(self.s-8,1,1);m.w(self.s-4,self.block_size+12)
        lease=self.s+L['RvSession.leases']
        for offset,value in [(0,1),(4,~1),(8,self.s),(12,self.block_size)]:m.w(lease+offset,value)
        for member,value in [('image_address',I),('image_bytes',len(DAT)),('bss_bytes',1068),
          ('capabilities',(1<<17)|(1<<19)),('code_begin',256),('code_end',11852)]:
            self.sw(member,value)
        for i in range(12):m.w(self.s+L['RvSession.bindings']+4*i,1)
        unit=name.encode().ljust(8,b'\0')+version.to_bytes(2,'big')+b'\0\0'
        m.put(self.s+L['RvSession.unit'],unit);m.put(R+L['RvRoot.unit'],unit)
        m.put(0x2040f81c,unit[:8]);m.w(0x2040f81c+44,version,2);m.w(0x2040f81c+46,0,2)
        m.w(0x2022f71c,5,1);m.w(0x2022f720,0x2022f56c)
        m.w(0x2022f5a8,0x2022d610);m.w(0x2022f5ac,7,1)
        m.w(0x2022f725,1,1);m.w(0x2022f726,1,1)
        m.w(0x205d9bf8,8);m.w(0x205d9c00,56)
        m.w(0x205a280f,2,1);m.w(0x205a27d8,0x205a279c)
        m.w(0x205a27d4,1,1);m.w(0x205a279c,32,1)
        m.w(0x205a293c,0x2022f71c);m.w(0x2037f3bc,32)
        def result(value):
            return lambda x:x.assign('r0',value)
        m.edges={0x2005f228:lambda x:x.assign('r0',self.context_kind),
                 0x2009359c:lambda x:x.assign('r0',self.ready),
                 0x20094e2c:result(9),0x201dc180:result(0),
                 0x201fd360:result(0),0x201d73e0:self.ascii,
                 0x2009005c:self.rpc}
        assert self.entry('ig_bootstrap')==1
        assert self.entry('ig_init')==1

    def rw(self,key,value,size=4):self.m.w(R+L['RvRoot.'+key],value,size)
    def sw(self,key,value,size=4):self.m.w(self.s+L['RvSession.'+key],value,size)
    def nu(self,key,size=1):return self.m.u(self.n+L['Probe.'+key],size)

    def ascii(self,m):
        p,count,dest=m.regs[4:7]
        m.put(dest,m.get(p,count)+b'\0')
        if self.text_case:self.text_case(self)
        m.assign('r0',count)

    def rpc(self,m):
        assert m.regs[4]==8
        sp=m.regs[15]
        assert m.u(sp)==2
        cmd,value=m.u(sp+4),m.u(sp+8)
        assert cmd in (21,22,23)
        got=value
        if cmd==23:self.page=value
        elif cmd==21:
            self.cursor=(self.page<<16)|(value&0xfffe)
            got=self.cells.get(self.cursor,0)
        elif cmd==22:
            old=self.cells.get(self.cursor,0)
            if not self.ignore_w:self.cells[self.cursor]=value
            self.writes.append((self.cursor,old,value,not self.ignore_w))
            self.cursor+=2
        row={'command':cmd,'value':value,'page':self.page,'cursor':self.cursor,'result':got}
        if self.rpc_case:
            forced=self.rpc_case(self,row)
            if forced is not None:row['result']=got=forced
        self.rpc_log.append(row)
        m.assign('r0',got)

    def entry(self,name,keep=0):
        m=self.m;q=self.s+L['RvSession.call_request'];reply=self.s+L['RvSession.call_reply']
        m.put(q,b'\0'*64);m.w(q,1,2);m.w(q+2,64,2)
        fields={0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,
                10:self.s+L['RvSession.context'],11:L['RvPrivateContext.size']}
        if name=='ig_event':fields.update({8:7,9:keep})
        for index,value in fields.items():m.w(q+8+4*index,value)
        result=m.run(m.names[name],(0,1,q,reply))
        if name=='ig_menu' and result==1:
            m.w(0x205a27d4,2,1);m.w(0x205a27a4,33,1);m.w(0x205a27a8,0x2022f71c)
        return result

    def rows(self):
        m=self.m;at=self.n+L['Probe.rows']
        rows=[m.get(at+9*i,9).split(b'\0')[0].decode('ascii') for i in range(8)]
        assert len(rows)==8 and all(1<=len(r)<=8 for r in rows),rows
        return rows

    def visible(self):
        m=self.m;count=m.u(0x2022f5ac,1);base=m.u(0x2022f5a8)
        assert count==8,count
        rows=[]
        for i in range(8):
            p=m.u(m.u(base+4*i));rows.append(m.get(p,70).split(b'\0')[0].decode('ascii'))
        assert len(rows)==8 and all(1<=len(r)<=8 for r in rows),rows
        return rows

    def open(self):
        assert self.entry('ig_menu')==1
        assert self.rows()==self.visible()
        return self.rows()

    def disp(self):
        assert self.entry('ig_panel_open')==1
        return self.rows()

    def twice(self):self.disp();return self.disp()

    def service(self,op,extra=None):
        m=self.m;q=self.s+L['RvSession.call_request'];reply=self.s+L['RvSession.call_reply']
        m.put(q,b'\0'*64);m.w(q,1,2);m.w(q+2,64,2)
        fields={0:1,1:m.u(self.s+L['RvSession.rpc_token']),2:1,3:1,4:1,5:1,6:1,7:1}
        fields.update(extra or {})
        for index,value in fields.items():m.w(q+8+4*index,value)
        return m.run(m.names['rv_call'],(4,op,q,reply))

    def summary(self):
        allowed=[(R,R+256),(self.s,self.s+self.block_size),(0x206fe000,0x20700000),
                 (0x2022f5a8,0x2022f5b0),(0x2022f725,0x2022f727),(0x205a2944,0x205a2945)]
        outside=[(hex(a),size) for a,size in self.m.write_cells if not any(lo<=a and a+size<=hi for lo,hi in allowed)]
        assert not outside,outside
        return {'rows':self.rows(),'cell':hex(self.cells[0x2012ebe0]),
                'writes':self.writes,'rpc_count':len(self.rpc_log),
                'write_count':self.nu('writes',2),'sets':self.nu('sets'),'view':self.nu('view'),
                'store_addresses_outside_reviewed_ranges':outside,
                'instruction_packets':self.m.count,'store_count':self.m.store_count}


class Combined(Session):
    def __init__(self):
        self.unit=Unit()
        super().__init__()

    def rpc(self,m):
        sp=m.regs[15]
        assert m.regs[4]==8 and m.u(sp)==2
        cmd,value=m.u(sp+4),m.u(sp+8)
        if cmd==23:self.page=value
        at=self.unit.m.u(0x20246158)
        old=self.unit.m.u(at,2) if cmd==22 else 0
        got=self.unit.call(cmd,value)
        if cmd==22:self.writes.append((at,old,value,self.unit.m.u(at,2)==value))
        self.cursor=self.unit.m.u(0x20246158)
        for address in (0x2012ebe0,0x2012ebe2):self.cells[address]=self.unit.m.u(address,2)
        for offset in (0x3b06,0x3b10,0x3b00):self.cells[0x12c00000+offset]=self.unit.m.u(self.unit.t+offset,2)
        row={'command':cmd,'value':value,'page':self.page,'cursor':self.cursor,'result':got}
        if self.rpc_case:
            forced=self.rpc_case(self,row)
            if forced is not None:row['result']=got=forced
        self.rpc_log.append(row);m.assign('r0',got)


def main():
    results={}
    s=Session();assert s.open()[0]=='P1 ORIG'
    assert s.disp()[0]=='SWITCH?' and not s.writes
    assert s.entry('ig_apply')==1 and s.rows()[0]=='P1 ORIG' and not s.writes
    assert s.twice()[0]=='P1 MOD' and s.cells[0x2012ebe0]==0x7fff
    assert s.entry('ig_event')==2 and s.cells[0x2012ebe0]==0x7fff
    assert s.open()[0]=='P1 MOD'
    assert s.twice()[0]=='P1 ORIG' and s.cells[0x2012ebe0]==0xffff
    results['normal']=s.summary()
    assert all(a==0x2012ebe0 and (old,new) in ((0xffff,0x7fff),(0x7fff,0xffff)) for a,old,new,_ in s.writes)
    for name in ('qlaunch','l08firm'):
        s=Session(name);assert s.open()[0]=='ONLY50MM';s.twice();s.entry('ig_apply')
        assert not s.rpc_log and not s.writes
        results[name]=s.summary()
    for label,address,value in [('T_guard',0x12c03b06,0x8000),('D_guard',0x2012ebe2,0x1234),
                                 ('unknown',0x2012ebe0,0x1234)]:
        s=Session();s.cells[address]=value;s.open();s.twice();assert not s.writes
        results[label]=s.summary()
    s=Session();s.open()
    def lose_page(x):x.m.w(0x205d9bf8,0)
    s.text_case=lose_page;s.disp();assert s.nu('view')==0 and not s.writes
    s.text_case=None;s.m.w(0x205d9bf8,8)
    assert s.disp()[0]=='SWITCH?' and not s.writes
    results['confirm_publish_failure']=s.summary()
    s=Session();s.open();s.disp();s.cells[0x12c03b06]=0x8000;s.disp()
    assert not s.writes and s.rows()[-1]=='SW ERR 2'
    results['guard_change']=s.summary()
    s=Session();s.open();s.ignore_w=True;s.twice()
    assert s.cells[0x2012ebe0]==0xffff and s.rows()[-1]=='SW ERR 3'
    results['write_not_stored']=s.summary()
    s=Session();s.open();s.twice();s.ignore_w=True;s.twice()
    assert s.cells[0x2012ebe0]==0x7fff and s.rows()[-1]=='SW ERR 3'
    s.ignore_w=False;s.twice();assert s.cells[0x2012ebe0]==0xffff
    results['restore_retry']=s.summary()
    s=Session();s.open()
    for i in range(16):
        assert s.twice()[0]=='P1 MOD'
        if i<15:assert s.twice()[0]=='P1 ORIG'
    assert s.twice()[0]=='P1 ORIG' and s.rows()[-1]=='SW LIMIT'
    count=len(s.writes);s.twice();assert len(s.writes)==count==32
    results['limit']=s.summary()
    s=Session();s.open();s.twice();assert s.entry('ig_stop')==1
    assert s.cells[0x2012ebe0]==0xffff and s.entry('ig_stop')==3
    results['stop']=s.summary()
    s=Session();s.ready=0;assert s.open()[0]=='P1 ER 04';assert not s.rpc_log
    results['not_ready']=s.summary()
    s=Session();s.rpc_case=lambda _,row:-1 if row['command']==21 and row['value']==0x3b06 else None
    assert s.open()[0]=='P1 ER 01';s.twice();assert not s.writes
    results['read_failure']=s.summary()
    s=Session();s.open();s.disp()
    s.rpc_case=lambda _,row:0x1234 if row['command']==21 and row['value']==0xebe0 else None
    s.disp();assert not s.writes and s.rows()[-1]=='SW ERR 2'
    results['old_value_changed']=s.summary()
    s=Session();s.open();s.disp();s.sw('capabilities',1<<17);s.disp()
    assert not s.writes and s.rows()[-1]=='SW ERR 5'
    results['write_capability_missing']=s.summary()
    s=Session();s.open()
    for _ in range(8):s.twice();s.twice()
    assert s.nu('writes',2)==16 and s.disp()[6]=='WRITES F'
    results['write_count_display']=s.summary()
    s=Combined();assert s.open()[0]=='P1 ORIG';s.twice()
    assert s.rows()[0]=='P1 MOD' and s.unit.m.u(0x2012ebe0,2)==0x7fff
    s.twice();assert s.unit.m.u(0x2012ebe0,2)==0xffff
    results['original_unit_set_restore']=s.summary()
    s=Combined();s.open();s.rpc_case=lambda _,row:-1 if row['command']==22 else None
    s.twice();assert s.rows()[0]=='P1 MOD' and s.rows()[-1]=='SW ERR 3'
    assert s.unit.m.u(0x2012ebe0,2)==0x7fff
    failed=s.summary()
    count=len(s.rpc_log);assert s.entry('ig_event')==2 and len(s.rpc_log)==count
    after_ok=s.summary()
    assert s.open()[0]=='P1 MOD' and s.unit.m.u(0x2012ebe0,2)==0x7fff
    results['changed_value_with_reply_failure']={'after_reply':failed,'after_OK':after_ok,'after_reopen':s.summary()}
    s=Session();s.open();start=len(s.rpc_log)
    for op in (2,3,4):assert s.service(op)==-4
    assert s.service(1)==0
    assert s.service(7,{8:0x2012ebe2})==-3
    assert s.service(7,{9:0x1234})==-3
    assert s.service(5)==0 and len(s.rpc_log)==start and not s.writes
    results['fixed_service_parameters']=s.summary()
    er_pages={}
    for number in range(1,8):
        s=Session();s.open();s.m.w(s.n+L['Probe.have'],0,1);s.m.w(s.n+L['Probe.fail'],number,1)
        assert s.entry('ig_apply')==1
        assert s.visible()[0]=='P1 ER %02X'%number
        er_pages[str(number)]=s.visible()
    results['error_page_formats']={'boundary':'The seven formatter error states are set in model memory; this does not represent seven transport failures.','rows':er_pages}
    (HERE/'replay.json').write_text(json.dumps({'boundary':'Final DAT instructions; native UI and RPC transport are models. Combined cases also execute original unit X/V/W routines with modeled string functions. Resident hooks and the unit OS are not run.',
                                            'cases':results},ensure_ascii=False,indent=2)+'\n')
    print('PASS:',', '.join(results))


if __name__=='__main__':main()
