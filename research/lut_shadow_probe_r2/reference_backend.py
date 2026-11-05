"""Adapt the existing GNU reference CPU's public map/call interface to fixtures.

No instruction or device implementation is replaced. Overlapping fixture maps
are split into disjoint regions before the existing reference CPU sees them.
"""
from collections import deque
import json
import os
import sys
import time
import common as C

os.environ.update(GXR_FAST_BACKEND='reference',GXR_FAST_POLICY='strict',GXR_FAST_MODE='fast',
                  GXR_EMULATOR_BATCH='1',GXR_FAST_MODEL_FIXES='')
sys.path.insert(0,str(C.ROOT/'tools/gxr_emulator_fast/strict_r4'))
from backend import Backend
sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'))
from backend_api import WriteEvent

class ReferenceBackend(Backend):
    def __init__(self):
        super().__init__(mode='fast')
        self.set_batch(True)
        cfg=json.loads((C.LOCAL/'harness.json').read_text())
        # Session.seal identifies this exact stack region by its base.
        self.map_boundaries={cfg['stack_base'],cfg['stack_base']+cfg['stack_bytes']}
        self.rows={}; self.tail=deque(maxlen=16); self.traces=[]
        self.admitted_instructions=0
        self.native_stats=dict(engine='GNU reference',library_sha256=C.sha(self.library_path.read_bytes()),
            calls=0,instructions=0)

    @property
    def total_steps(self): return self.steps

    def map(self,base,data,writable=True):
        self.materialize_native()
        data=bytearray(data); end=base+len(data); self._range(base,len(data))
        result=[]
        for old,buffer,write in self.regions:
            last=old+len(buffer)
            if end<=old or last<=base: result.append((old,buffer,write)); continue
            if old<base: result.append((old,buffer[:base-old],write))
            if end<last: result.append((end,buffer[end-old:],write))
        if data: result.append((base,data,bool(writable)))
        self.regions=self.coalesce(result)
        self.lib.gxr_flush(self.handle)

    def coalesce(self,regions):
        merged=[]
        for base,data,writable in sorted(regions,key=lambda row:row[0]):
            if merged and merged[-1][0]+len(merged[-1][1])==base and merged[-1][2]==writable and base not in self.map_boundaries:
                old,previous,flag=merged[-1]
                # Do not extend an existing buffer: a saved map can still
                # reference it during the capture whitelist's restoration.
                merged[-1]=(old,previous+data,flag)
            else: merged.append((base,data,writable))
        return merged

    def _sync(self,pcs):
        assert len(self.regions)<=32, 'GNU shared-RAM region capacity exceeded'
        return super()._sync(pcs)

    def add_write_trace(self,lo,hi,callback):
        self.traces.append((lo,hi,callback))

    def call(self,addr,args,lr_sentinel,max_steps):
        self.write_traces=[]
        for lo,hi,callback in self.traces:
            def wrote(address,data,callback=callback):
                callback(WriteEvent(address,bytes(data),self._pc,'cpu'))
            super().add_write_trace(lo,hi,wrote)
        for i,value in enumerate(args): self.set_reg('r'+str(i),value)
        self.set_reg('pc',addr); self.set_reg('lr',lr_sentinel)
        previous=self.breakpoints.get(lr_sentinel)
        self.add_breakpoint(lr_sentinel,lambda _:True)
        total=0
        try:
            while total<max_steps:
                if not self.admitted_instructions:
                    while True:
                        try: C.gate('GNU-reference-chunk'); break
                        except RuntimeError as error:
                            if not str(error).startswith('LOAD_DEFERRED'): raise
                            C.save(C.LOCAL/('reference-progress-'+str(os.getpid())+'.json'),dict(status='LOAD_DEFERRED',function=addr,steps=total))
                            time.sleep(20)
                    self.admitted_instructions=16000000
                # A short function can return before using its admitted
                # instruction batch. Carry only the remaining allowance to
                # the next call; execute every instruction and keep each
                # call's original max_steps bound.
                result=self.run(min(self.admitted_instructions,max_steps-total)); total+=result.steps
                self.admitted_instructions=max(0,self.admitted_instructions-result.steps)
                C.save(C.LOCAL/('reference-progress-'+str(__import__('os').getpid())+'.json'),dict(status='RUNNING',function=addr,steps=total,pc=result.pc))
                if result.reason=='breakpoint' and result.pc==lr_sentinel: result.reason='return'
                if result.reason!='max_steps': break
            result.steps=total
            self.native_stats['calls']+=1; self.native_stats['instructions']+=total
            self.native_stats['batch_stats']=dict(self.batch_stats)
            self.native_stats['maximum_regions']=max(self.native_stats.get('maximum_regions',0),len(self.regions))
            if result.reason=='fault': self.tail.extend(self.trace)
            return result
        finally:
            if previous is None:self.breakpoints.pop(lr_sentinel,None)
            else:self.breakpoints[lr_sentinel]=previous
