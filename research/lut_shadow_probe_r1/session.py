"""Final-DAT instruction fixture. Native tick/font/encoder boundaries are explicit models."""
from pathlib import Path
import json
import os
import struct
import sys
import common as C
import schema as S
from types import SimpleNamespace

class Session:
    def __init__(self,backend):
        os.environ['GXR_HARNESS_BACKEND']=backend if backend in ('c','python') else 'python'
        sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'))
        import python_backend as P
        from image_loader import Image
        P.CACHE=C.LOCAL/'decode'/backend
        if backend=='reference':
            from reference_backend import ReferenceBackend
            self.cpu=ReferenceBackend()
        else: self.cpu=P.PythonBackend()
        self.backend=backend
        self.cfg=json.loads((C.LOCAL/'harness.json').read_text())
        self.layout=json.loads((C.ENGINE/'local/build/layout.json').read_text())
        self.off=json.loads((C.ENGINE/'local/build/offsets.json').read_text())
        self.raw=(C.PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
        assert C.sha(self.raw)==self.layout['dat_sha256']
        Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','lp_session_elf').Elf
        self.elf=Elf(C.ENGINE/'local/build/engine.elf')
        self.symbols={name:r['value'] for name,r in self.elf.symbols.items()}
        self.resident=Elf(C.RESIDENT/'local/resident/resident.elf')
        self.resident_symbols={name:r['value'] for name,r in self.resident.symbols.items()}
        self.image=Image(C.BODY,self.layout['body_sha256']); self.image.load(self.cpu)
        cfg=self.cfg
        self.cpu.map(cfg['stack_base'],bytes(cfg['stack_bytes']))
        self.cpu.map(cfg['heap_base'],bytes(cfg['heap_end']-cfg['heap_base']))
        self.cpu.set_reg('r15',cfg['stack_top']); self.cpu.set_reg('psw',64)
        self.root=self.off['root.address']; self.block=cfg['block']
        self.base=self.block+self.off['session.bytes']; self.state=self.base+self.symbols['lp']
        self.put(cfg['heap_begin_word'],cfg['heap_base']); self.put(cfg['heap_end_word'],cfg['heap_end'])
        self.put(cfg['heap_pool_word'],cfg['heap_end']-cfg['heap_base'])
        total=self.off['block.overhead']+self.layout['image_bss_bytes']
        self.put(self.block-12,0); self.put(self.block-8,1,1); self.put(self.block-4,total+12)
        self.cpu.write(self.root,bytes(self.off['root.size']))
        for name,value,size in (('magic',self.off['root.magic_value'],4),('version',self.off['root.version_value'],1),
            ('state',2,1),('inflight',1,1),('block',self.block,4),('inverse',self.block^0xffffffff,4),
            ('lease',1,4),('lease_inverse',0xfffffffe,4),('heap_begin',cfg['heap_base'],4),('heap_end',cfg['heap_end'],4),
            ('block_bytes',total,4),('alloc_bytes',total+12,4),('code_address',self.base+256,4),
            ('code_bytes',self.layout['engine_bytes'],4)):
            self.put(self.root+self.off['root.'+name],value,size)
        self.cpu.write(self.root+self.off['root.epoch'],struct.pack('>12I',*([1]*12)))
        identity=bytes.fromhex(cfg['unit_identity']); self.cpu.write(self.root+self.off['root.unit'],identity)
        self.cpu.write(cfg['unit_name'],identity[:8]); self.cpu.write(cfg['unit_name']+44,identity[8:])
        self.cpu.write(self.block+self.off['session.leases'],struct.pack('>5I',1,0xfffffffe,self.block,total,1))
        for name,value in (('image_address',self.base),('image_bytes',len(self.raw)),('bss_bytes',self.layout['bss_bytes']),
            ('code_begin',256),('code_end',256+self.layout['engine_bytes']),('generation',C.GENERATION),('capabilities',32767)):
            self.put(self.block+self.off['session.'+name],value)
        self.cpu.write(self.block+self.off['session.unit'],identity)
        image=bytearray(self.raw)+bytes(self.layout['bss_bytes'])
        for patch,target in self.layout['relocations']: struct.pack_into('>I',image,patch,self.base+target)
        self.cpu.write(self.base,image)
        # Keep instruction decoding within the immutable code/table mapping.
        # A heap-wide view also contains the resident's changing request lane.
        self.cpu.map(self.base+256,image[256:256+self.layout['engine_bytes']],False)
        self.context=self.block+self.off['session.context']
        self.q=self.block+self.off['session.call_request']; self.reply=self.block+self.off['session.call_reply']
        self.image_q=self.block+self.off['session.image_request']; self.image_reply=self.block+self.off['session.image_reply']
        self.ticks=100; self.tick_period=1; self.tick_reads=0; self.tick_step=1
        self.calls=[]; self.allocations=[]; self.encoder_calls=0; self.clobber_tick=True
        self.next_alloc=self.block+total+64
        self.stub('native_tick',self.tick)
        self.stub('native_context',lambda:0)
        self.stub('native_language',lambda:1)
        self.stub('native_ascii',self.ascii)
        self.stub('native_alloc',self.allocate)
        self.stub('native_draw',lambda:0)
        self.stub('native_encoder',self.encoder)
        self.request()
        assert self.invoke('ig_bootstrap',[0,1,self.q,self.reply],budget=10000000 if backend=='reference' else 2000000)==1
        assert self.u(self.reply+12)==40 and self.u(self.reply+28)==73
        assert self.u(self.reply+4)==0
        assert self.s('selftest')==1 and self.s('table_ok')==1
        self.put(self.root+self.off['root.state'],3,1)
        self.put(self.block+self.off['session.capabilities'],32767+(1<<17)+(1<<20))
        self.seed_ui()
        value=self.resident_call('rv_code_guard',[self.base+256,self.layout['engine_bytes']])
        self.put(self.root+self.off['root.code_crc'],value)

    def u(self,at,size=4): return int.from_bytes(self.cpu.read(at,size),'big')
    def put(self,at,value,size=4): self.cpu.write(at,(value&((1<<(size*8))-1)).to_bytes(size,'big'))
    def s(self,name): return self.u(self.state+self.off['state.'+name])
    def set_s(self,name,value): self.put(self.state+self.off['state.'+name],value)
    def sample(self,index):
        base=self.state+self.off['state.samples']+index*self.off['sample.size']
        return {name:self.u(base+self.off['sample.'+name]) for name in S.SAMPLE}
    def references(self):
        base=self.state+self.off['state.refs']
        return [{name:self.u(base+i*self.off['reference.size']+self.off['reference.'+name]) for name in S.REFERENCE} for i in range(self.s('ref_count'))]
    def text(self):
        self.invoke('lp_rows')
        raw=self.cpu.read(self.state+self.off['state.text'],320)
        return [raw[i*40:(i+1)*40].split(b'\0')[0].decode('ascii') for i in range(8)]
    def stub(self,key,fn):
        def callback(cpu):
            value=fn()
            cpu.set_reg('r0',value&0xffffffff); cpu.set_reg('pc',cpu.get_reg('r14'))
            return False
        self.cpu.add_breakpoint(self.cfg[key],callback)
    def tick(self):
        self.tick_reads+=1
        if self.tick_reads%self.tick_period==0: self.ticks=(self.ticks+self.tick_step)&0xffffffff
        if self.clobber_tick:
            for i in range(8,14): self.cpu.set_reg('r'+str(i),0xdead0000+i)
        return self.ticks
    def ascii(self):
        source=self.cpu.get_reg('r4'); source_bytes=self.cpu.get_reg('r5')
        target=self.cpu.get_reg('r6'); language=self.cpu.get_reg('r7'); capacity=2*source_bytes+1
        raw=self.cpu.read(source,40).split(b'\0')[0]
        assert len(raw)==source_bytes and language==1, 'native ASCII ABI is source, source bytes, glyphs, language'
        out=b''.join(bytes((1,c)) for c in raw)+b'\0'
        assert len(out)<=capacity
        self.cpu.write(target,out)
        return 0
    def allocate(self):
        count=self.cpu.get_reg('r4'); base=self.next_alloc; self.next_alloc+=(count+15)&~3
        assert self.next_alloc<self.cfg['heap_end']
        self.put(base-12,0); self.put(base-8,1,1); self.put(base-4,(count+15)&~3)
        self.allocations.append(dict(base=base,bytes=count)); return base
    def encoder(self):
        self.encoder_calls+=1
        assert self.cpu.get_reg('r4')==self.cfg['k']
        self.ticks=(self.ticks+20)&0xffffffff
        return 0
    def request(self,values=None,image=False):
        q=self.image_q if image else self.q; reply=self.image_reply if image else self.reply
        args=[1,1]+[self.u(self.root+self.off['root.epoch']+4*i) for i in (0,1,2,3,6,7)]+[0]*6
        args[10]=self.context; args[11]=self.off['context.size']
        for i,value in (values or {}).items(): args[i]=value
        self.cpu.write(q,struct.pack('>HHI14I',1,64,0,*args)); self.cpu.write(reply,bytes(32))
        return q,reply
    def invoke(self,name,args=(),budget=2000000,extra=()):
        sp=self.cpu.get_reg('r15')
        for i,value in enumerate(extra): self.put(sp+4*i,value)
        stop=self.cpu.call(self.base+self.symbols[name],list(args),self.cfg['stop'],budget)
        self.calls.append(dict(name=name,reason=stop.reason,steps=stop.steps,detail=stop.detail))
        assert stop.reason=='return',(name,stop,list(self.cpu.tail)[-10:])
        assert self.cpu.get_reg('r15')==sp,(name,'stack imbalance')
        return self.cpu.get_reg('r0')
    def resident_call(self,name,args=(),budget=2000000,stop=None):
        sp=self.cpu.get_reg('r15')
        observed=self.cpu.call(self.resident_symbols[name],list(args),stop or self.cfg['stop'],budget)
        self.calls.append(dict(name='resident.'+name,reason=observed.reason,steps=observed.steps,detail=observed.detail))
        assert observed.reason=='return',(name,observed,list(self.cpu.tail)[-10:])
        assert self.cpu.get_reg('r15')==sp,(name,'stack imbalance')
        return self.cpu.get_reg('r0')
    def seed_ui(self):
        cfg=self.cfg
        for key,value,size in (('activity',8,4),('view',56,4),('part',1,1),('views_count',1,1),
            ('views_array_word',cfg['views_array'],4),('names_word',cfg['native_names'],4),('names_count',7,1),
            ('cursor1',1,1),('cursor2',1,1)):
            self.put(cfg[key],value,size)
        self.put(cfg['views_array'],32,1); self.put(cfg['views_array']+4,cfg['native_state'])
        self.put(cfg['native_state'],5,1); self.put(cfg['native_state']+4,cfg['native_descriptor'])
    def menu(self):
        self.request(); result=self.invoke('ig_menu',[0,1,self.q,self.reply])
        return result,self.text()
    def move(self,row):
        self.request({8:row}); return self.invoke('ig_apply',[0,1,self.q,self.reply])
    def ok(self):
        self.request({8:7,9:0,12:self.cfg['event_caller'],13:35})
        return self.invoke('ig_event',[0,1,self.q,self.reply])
    def calibrate(self):
        for _ in range(2):
            self.invoke('lp_reference_start'); self.ticks=(self.ticks+30000)&0xffffffff
            self.invoke('lp_reference_stop')
        assert self.s('stage')==1 and self.s('locked')==0
    def arm(self,stage): return self.invoke('lp_arm',[stage])
    def frame(self,data=None):
        cfg=self.cfg
        if data is None:
            pattern=bytes(range(256))*64
            data=(pattern*((24430080+len(pattern)-1)//len(pattern)))[:24430080]
        self.frame_bytes=data; self.frame_hash=C.sha(data)
        self.cpu.map(cfg['frame_base'],data,False)
        self.put(cfg['k']+332,cfg['frame_base'])
        self.put(cfg['k']+340,8576,2); self.put(cfg['k']+342,4288,2); self.put(cfg['k']+344,2848,2)
        self.put(cfg['stack_top']+4,cfg['outer'])
        self.frame_ready=True
    def seal(self,reply):
        saved=list(self.cpu.regions)
        self.cpu.regions[:]=[(base,data,base==self.cfg['stack_base']) for base,data,_ in saved]
        bss=self.base+len(self.raw)
        self.cpu.map(bss,self.cpu.read(bss,self.layout['bss_bytes']),True)
        self.cpu.map(reply,self.cpu.read(reply,32),True)
        return saved
    def unseal(self,saved,reply):
        bss=self.base+len(self.raw); state=self.cpu.read(bss,self.layout['bss_bytes']); rep=self.cpu.read(reply,32)
        self.cpu.regions[:]=saved; self.cpu.rows.clear()
        self.cpu.write(bss,state); self.cpu.write(reply,rep)
    def capture(self,encoder=4,budget=4000000000,h41=True,geometry=None):
        if not getattr(self,'frame_ready',False): self.frame()
        cfg=self.cfg
        if geometry:
            for at,value,size in geometry: self.put(at,value,size)
        q,reply=self.request({8:40,9:cfg['k'],12:cfg['stack_top'],13:cfg['native_encoder']},True)
        original_k=self.cpu.read(cfg['k'],588)
        saved=self.seal(reply)
        try:
            assert self.invoke('ig_panel_abort',[0,1,q,reply],budget)==1
            assert self.u(reply+28)==1
        finally: self.unseal(saved,reply)
        assert self.cpu.read(cfg['k'],588)==original_k
        assert C.sha(self.cpu.read(cfg['frame_base'],len(self.frame_bytes)))==self.frame_hash
        if h41:
            self.ticks=(self.ticks+20)&0xffffffff
            q,reply=self.request({8:41,9:cfg['k'],13:encoder},True)
            saved=self.seal(reply)
            try: assert self.invoke('ig_panel_abort',[0,1,q,reply])==0
            finally: self.unseal(saved,reply)
        assert C.sha(self.cpu.read(cfg['frame_base'],len(self.frame_bytes)))==self.frame_hash
        self.invoke('lp_reconcile')
        return self.sample(self.s('used')-1) if self.s('used') else None
    def capture_bridge(self,budget=4000000000):
        """Actual v3.10 H40 trampoline -> DAT -> declared encoder -> H41 -> DAT."""
        if not getattr(self,'frame_ready',False): self.frame()
        cfg=self.cfg; root=self.root; session=self.block
        self.put(root+self.off['root.inflight'],0,1)
        self.put(root+self.off['root.image_state'],0)
        # Declare the encoder's observed native word as nonzero while the
        # wrapper model itself returns zero. Keep it readonly during DAT.
        self.put(cfg['encoder_status'],4)
        self.cpu.set_reg('r0',cfg['native_encoder']); self.cpu.set_reg('r8',cfg['k'])
        self.cpu.set_reg('r5',cfg['k']+452)
        original_k=self.cpu.read(cfg['k'],588); root_before=self.cpu.read(root,self.off['root.size'])
        original_session=self.cpu.read(session,self.off['session.size'])
        saved=self.seal(self.image_reply)
        self.cpu.map(root,root_before,True); self.cpu.map(session,original_session,True)
        bad=[]; dat_stores=[0]
        def monitor(event):
            if event.pc is not None and self.base+256<=event.pc<self.base+256+self.layout['engine_bytes']:
                dat_stores[0]+=1
                if not self.image_reply<=event.address or event.address+len(event.data)>self.image_reply+32:
                    bad.append(dict(pc=event.pc,address=event.address,bytes=len(event.data)))
                    raise AssertionError(('DAT write outside capture whitelist',bad[-1]))
        capture_mmio=[]
        if self.backend in ('c','python'):
            # Only root/session accesses cross into Python. Stack and private
            # row stores retain the existing fast RAM path, with the same
            # readonly fence for every other native byte.
            def backed_read(at,count):
                lo,data,_=self.cpu._region(at,count)
                return bytes(data[at-lo:at-lo+count])
            def backed_write(at,data):
                pc=self.cpu.writer_pc
                assert pc is not None and pc!=0, 'missing target writer PC'
                monitor(SimpleNamespace(address=at,data=data,pc=pc))
                lo,buffer,_=self.cpu._region(at,len(data))
                buffer[at-lo:at-lo+len(data)]=data
            for lo,size in ((root,self.off['root.size']),(session,self.off['session.size'])):
                self.cpu.add_mmio(lo,lo+size,backed_read,backed_write)
                capture_mmio.append((lo,lo+size))
        else:
            self.cpu.add_write_trace(root,root+self.off['root.size'],monitor)
            self.cpu.add_write_trace(session,session+self.off['session.size'],monitor)
        encoder_before=self.encoder_calls
        try:
            assert self.resident_call('rv_hook_40',budget=budget,stop=cfg['native_return'])==0
            assert self.encoder_calls==encoder_before+1
            assert self.u(root+self.off['root.image_state'])==0
            assert self.u(root+self.off['root.state'],1)==3
            assert not bad
        finally:
            newroot=self.cpu.read(root,self.off['root.size']); newsession=self.cpu.read(session,self.off['session.size'])
            self.cpu.traces[:]=[trace for trace in self.cpu.traces if trace[2] is not monitor]
            if capture_mmio:
                self.cpu.mmio[:]=[entry for entry in self.cpu.mmio if entry[:2] not in capture_mmio]
            self.unseal(saved,self.image_reply)
            self.cpu.write(root,newroot); self.cpu.write(session,newsession)
            self.put(root+self.off['root.inflight'],1,1)
        assert self.cpu.read(cfg['k'],588)==original_k
        assert C.sha(self.cpu.read(cfg['frame_base'],len(self.frame_bytes)))==self.frame_hash
        self.invoke('lp_reconcile')
        sample=self.sample(self.s('used')-1) if self.s('used') else None
        self.last_bridge=dict(actual_resident=True,encoder_calls=self.encoder_calls-encoder_before,
            DAT_session_stores=dat_stores[0],bad_stores=bad,source_unchanged=True,K_unchanged=True)
        return sample
