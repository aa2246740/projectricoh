"""Trace real DAT instructions and their native callees, including same-value stores."""
from collections import Counter
import re
from native_support import *

FILES = {0x200a40b4:'open',0x200a449c:'read',0x200a437c:'close',0x200a544c:'create',
         0x200a45e8:'write',0x200a49d8:'rename',0x200a4910:'delete'}
SETTERS = {0x202871dc:'Image continuation',0x202bb96c:'native H08',
           0x20268768:'Image setter store',0x20268774:'Image row store'}


class Audit:
    def __init__(self,h,p,arm):
        self.h,self.p=h,p
        self.active=False
        self.armed=False
        self.entries=[]
        self.services=[]
        self.calls=[]
        self.native_bridges=[]
        self.writes=[]
        self.host_ui=[]
        self.setter_hits=[]
        self.captures=[]
        self.control_buffers=[]
        self.ui_op=None
        self.ui_entries=[]
        self.draws=[]
        self.irq=[]
        self.capture_active=False
        self.capture_reads=[]
        self.capturing_load=False
        self.capture_pc_range=(0,0)
        self.external=False
        self.external_writes=[]
        self.capture_pass_hook=None
        self.read_original=h.b.read
        self.field_at={int(v[0],16):(key,v[1]) for key,v in LAYOUT['fields'].items()}
        self.initial_settings=h.b.read(h.settings,0xc9e)
        arm[0]=self.enter
        h.b.add_write_trace(0,2**32,self.write)
        for pc,name in FILES.items():self.bp(pc,lambda b,name=name:self.native_call(b,'file',name))
        for pc,name in SETTERS.items():self.bp(pc,lambda b,name=name:self.setter(b,name))
        self.bp(0x2009005c,lambda b:self.native_call(b,'ipc',b.core.r[4]))
        self.bp(0x2005e034,lambda b:self.native_call(b,'queue_send',b.core.r[4]))
        self.bp(0x2005de00,lambda b:self.native_call(b,'delay',0))
        self.bp(0x201ffb2c,lambda b:self.row_draw(b))

    def bp(self,pc,callback):
        self.h.b.breakpoints.setdefault(pc,[]).insert(0,callback)

    def arm_error_page(self,arm):
        original=arm[0];fired=[False]
        def arm_error():
            original()
            if getattr(self.p,'error_armed',False):return
            self.p.error_armed=True
            def fail(b):
                if not fired[0] and b.core.r[0]==11 and b.core.r[1]==1 and private(self.h,self.p,'captured',1):
                    fired[0]=True;b.core.r[0]=0xffffffff;b.set_reg('pc',b.core.r[14])
                return False
            self.h.b.add_breakpoint(symbol(self.p,'rv_call'),fail)
        arm[0]=arm_error
        return fired

    def enter(self):
        h,p=self.h,self.p
        if not self.armed:
            self.armed=True
            self.bp(symbol(p,'rv_call'),self.service)
            assembly=(ENGINE/'candidate/engine_services/bridges.S').read_text()
            for name,target in re.findall(r'^\s+NATIVE (\w+),(0x[0-9a-f]+)',assembly,re.M):
                offset=p.elf.symbols[name];raw=p.dat[offset:offset+8]
                assert raw[:2]==bytes.fromhex('d6c0') and raw[4:6]==bytes.fromhex('86e6'),(name,raw.hex())
                actual=int.from_bytes(raw[2:4],'big')<<16|int.from_bytes(raw[6:8],'big')
                assert actual==int(target,16)
                self.bp(p.image_base+offset,lambda b,actual=actual:self.native_bridge(b,actual))
            self.bp(symbol(p,'ui_list'),self.ui)
            self.bp(symbol(p,'rv_native_draw'),self.draw)
            self.bp(symbol(p,'rv_irq_save'),lambda b:self.irq_call(b,'save'))
            self.bp(symbol(p,'rv_irq_restore'),lambda b:self.irq_call(b,'restore'))
            self.bp(symbol(p,'capture'),self.capture)
            pc=symbol(p,'capture')
            # The next ELF symbol bounds this non-inlined sampling function.
            # Local branch labels can lie inside a function. Read ELF st_size.
            parsed=load(ROOT/'firmware/stage2l_switch/tools/build.py','diag_trace_elf').Elf(ELF)
            info=parsed.symbols['capture']
            end=pc+info['size']
            self.capture_pc_range=(pc,end)
            h.b.read=self.read
        self.active=True
        target=h.b.core.r[0]
        self.control_buffers.extend(((h.b.core.r[3],64),(h.u(h.b.core.r[15]),32)))
        names=[name for name,value in p.elf.symbols.items() if p.image_base+value==target]
        self.entries.append(dict(pc=hex(target),names=names,psw=h.b.core.psw))
        ret=h.b.core.r[14];once=[True]
        def returned(b):
            if once[0]:once[0]=False;self.active=False
            return False
        self.bp(ret,returned)

    def service(self,b):
        if self.active:
            self.services.append(dict(id=b.core.r[0],op=b.core.r[1],pc=hex(b.pc),psw=b.core.psw))
        return False

    def ui(self,b):
        # LTO specializes ui_list's arguments. The wire request is authoritative.
        self.ui_op=self.services[-1]['op']
        at=symbol(self.p,'n')+N_OFFSETS['list']
        self.ui_entries.append(dict(op=self.ui_op,rows=self.h.u(at+20),psw=b.core.psw))
        ret=b.core.r[14];once=[True]
        def done(b):
            if once[0]:once[0]=False;self.ui_op=None
            return False
        self.bp(ret,done)
        return False

    def irq_call(self,b,kind):
        if self.active:
            self.irq.append(dict(kind=kind,psw=b.core.psw,argument=b.core.r[0] if kind=='restore' else None,
                                 caller=hex(b.core.r[14]),ui_op=self.ui_op))
        return False

    def draw(self,b):
        self.draws.append(dict(active=self.active,psw=b.core.psw,ui_op=self.ui_op,
                              activity=self.h.u(0x205d9bf8),state=self.h.u(0x205d9c00),
                              rows=self.h.u(0x2022f5ac,1)))
        return False

    def row_draw(self,b):
        return False

    def setter(self,b,name):
        self.setter_hits.append(dict(name=name,pc=hex(b.pc),active=self.active,rows=self.h.u(0x2022f5ac,1)))
        return False

    def native_call(self,b,kind,name):
        if self.active:
            self.calls.append(dict(kind=kind,name=name,pc=hex(b.pc),lr=hex(b.core.r[14])))
        return False

    def native_bridge(self,b,target):
        if self.active:
            self.native_bridges.append(dict(target=hex(target),caller=hex(b.core.r[14]),
                                            psw=b.core.psw))
        return False

    def write(self,e):
        ui=any(e.address<hi and e.address+len(e.data)>lo for lo,hi in UI_RANGES)
        if ui and e.origin not in ('cpu','model:native_memset'):
            self.host_ui.append(dict(address=hex(e.address),data=e.data.hex(),origin=e.origin))
        if self.active:
            record=(e.address,len(e.data),e.pc,e.origin,e.data.hex() if len(e.data)<=32 else 'bulk')
            (self.external_writes if self.external else self.writes).append(record)

    def capture(self,b):
        self.capture_active=True;self.capture_reads=[]
        ret=b.core.r[14];once=[True]
        def done(b):
            if once[0]:
                once[0]=False;self.capture_active=False
                self.captures.append(list(self.capture_reads))
            return False
        self.bp(ret,done)
        return False

    def read(self,at,n):
        value=self.read_original(at,n)
        lo,hi=self.capture_pc_range
        if self.capture_active and self.h.b.running and lo<=self.h.b.writer_pc<hi and at in self.field_at:
            key,width=self.field_at[at]
            if n==width:
                self.capture_reads.append(dict(field=key,address=hex(at),bytes=n,value=int.from_bytes(value,'big')))
                if len(self.capture_reads)==50 and self.capture_pass_hook:self.capture_pass_hook()
        return value

    def classify(self,event):
        address,nbytes,pc,origin,data=event
        h,p=self.h,self.p
        if any(address>=lo and address+nbytes<=hi for lo,hi in UI_RANGES):return 'native_ui'
        if 0x20054700<=address and address+nbytes<=0x20054800:return 'resident_private'
        block=h.u(pe.ROOT_ADDR+56);size=h.u(pe.ROOT_ADDR+104)
        if block and block<=address and address+nbytes<=block+size:return 'dat_private'
        ui=h.u(pe.ROOT_ADDR+136)
        if ui and ui<=address and address+nbytes<=ui+1968:return 'detached_ui'
        if ui and ui-12<=address and address+nbytes<=ui:return 'ui_allocator_header'
        if any(base<=address and address+nbytes<=base+size for base,size in self.control_buffers):return 'entry_control_buffer'
        if any(address>=lo and address+nbytes<=hi for lo,hi in (
                (0x206a0000,0x206b0000),(0x206e0000,0x20700000),(0x20698000,0x206a0000))):return 'task_stack'
        return 'UNAPPROVED'

    def result(self,check=True):
        classes=Counter();bad=[]
        for event in self.writes:
            category=self.classify(event);classes[category]+=1
            if category=='UNAPPROVED':
                a,n,pc,origin,data=event
                bad.append(dict(address=hex(a),bytes=n,pc=hex(pc) if pc is not None else None,origin=origin,data=data))
        calls=[e for e in self.calls if e['kind']=='file' or e['kind']=='delay' or
               e['kind']=='ipc' and e['name']==8 or e['kind']=='queue_send' and e['name']==2]
        actual_dat_sha=hashlib.sha256(self.p.dat).hexdigest()
        assert actual_dat_sha==sha(DAT),'Packaged DAT changed during replay'
        result=dict(status='PASS' if not (bad or calls or self.host_ui or self.setter_hits) else 'FAIL',
            dat_sha256=actual_dat_sha,body_sha256=self.h.image.sha256,
            elf_sha256=hashlib.sha256(self.p.elf.raw).hexdigest(),unit=self.p.unit,
            entries=self.entries,service_counts=dict(Counter(f"{s['id']}:{s['op']}" for s in self.services)),
            ui_entries=self.ui_entries,write_counts=dict(classes),unapproved_writes=bad,
            prohibited_calls=calls,all_native_calls=self.calls,native_setters=self.setter_hits,
            native_bridges=self.native_bridges,
            native_bridge_counts=dict(Counter(e['target'] for e in self.native_bridges)),
            host_ui_writes=self.host_ui,draws=self.draws,irq=self.irq,captures=self.captures,
            external_writes=self.external_writes,
            rpc8_calls=sum(e['kind']=='ipc' and e['name']==8 for e in self.calls),
            file_api_calls=sum(e['kind']=='file' for e in self.calls),
            queue2_sends=sum(e['kind']=='queue_send' and e['name']==2 for e in self.calls),
            settings_unchanged=self.h.b.read(self.h.settings,0xc9e)==self.initial_settings,
            resident_loader_file_calls=[e for e in self.p.native_log if e['op'] in ('open','read','close')])
        if check:
            assert not bad,bad[:12]
            assert not calls,calls
            assert not self.setter_hits,self.setter_hits
            assert not self.host_ui,self.host_ui
            assert all(int(e['target'],16) in (0x2005f228,0x201dc180,0x201d73e0,0x201fd360)
                       for e in self.native_bridges),self.native_bridges
            assert all(e['id'] in (10,11) for e in self.services),self.services
            assert all(e['rows']==8 for e in self.ui_entries),self.ui_entries
        return result
