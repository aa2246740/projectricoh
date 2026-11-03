#!/usr/bin/python3
"""Check all request words and native continuation using the exact r7 ELF."""
import importlib.util, json, signal, struct, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
saved=sys.argv[:]
sys.argv=[str(HERE/'prototype/tests/replay_h40.py'),str(HERE/'local/rebuild/v/r7/build'),
          str(HERE/'local/layout.log'),str(HERE/'local/unused.json')]
spec=importlib.util.spec_from_file_location('review_replay',HERE/'prototype/tests/replay_h40.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
sys.argv=saved

class Machine(replay.Machine):
    status_word=0
    legacy=False
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.put(0x2022f5a8,0x2022d610)
        self.cpu.write(0x2022f5ac,b'\x07')
        self.stops={replay.END,replay.RESUME,replay.RESUME_09,replay.RESUME_10}
        self.stops.update(replay.SYM[n] for n in replay.SYM if n.startswith(('rv_resume_','rv_skip_target_')))
        for address in self.stops:self.cpu.add_breakpoint(address,lambda _c:True)
    def dat(self,pc):
        q=self.r('r2')
        result=super().dat(pc)
        self.calls[-1]['header']=self.cpu.read(q,8).hex()
        if pc-self.image==256 and self.legacy:
            self.put(self.r('r3')+28,0)
        return result
    def n_wrapper(self):
        result=super().n_wrapper()
        self.put(replay.STATUS_WORD,self.status_word)
        return result
    def call(self,pc,regs,budget=200000):
        c=self.cpu
        for k,v in regs.items():c.set_reg(k,v)
        c.set_reg('pc',pc)
        for _ in range(64):
            c.run(budget);at=c.get_reg('pc')
            if at in self.stops:return at
            if at in self.native:c.set_reg('r0',self.native[at]()&0xffffffff)
            elif self.image and self.image<=at<self.image+320:c.set_reg('r0',self.dat(at)&0xffffffff)
            else:raise AssertionError(hex(at))
            c.set_reg('pc',c.get_reg('lr'))
        raise AssertionError('execution stop count exceeded')

def arguments():
    records=[]
    statuses=[0,1,0x7fffffff,0x80000000,0xffffffff]
    stack_addresses=[0x20462200,0x20464000,0x20465900]
    epochs=[0x10203040+i*0x01010101 for i in range(12)]
    for index,(outer,allowed) in enumerate(replay.RETURNS.items()):
        for j,sp in enumerate(stack_addresses):
            replay.NATIVE_SP=sp
            m=Machine()
            try:
                assert m.load()==0
                m.status_word=statuses[(index+j)%len(statuses)]
                for i,value in enumerate(epochs):m.put(replay.RV_ROOT+replay.RO['epoch']+4*i,value)
                m.policy['h40']='done'
                block=m.get(replay.RV_ROOT+replay.RO['block'])
                lease=m.get(replay.RV_ROOT+replay.RO['lease'])
                calls,regs=m.h40(outer)
                assert len(calls)==(2 if allowed else 1)
                for call in calls:
                    hook=call['hook']
                    expected=[lease,lease,*[epochs[n] for n in (0,1,2,3,6,7)],hook,replay.K,
                              block+replay.SO['context'],120,sp,replay.WRAPPER if hook==40 else m.status_word]
                    assert call['args']==expected,(call['args'],expected)
                    assert call['header']==struct.pack('>HHI',1,64,0).hex()
                    assert call['outer']==outer and sp-call['sp']==156
                expected_regs={f'r{i}':0x11000000+i*0x10101 for i in range(14)}
                expected_regs.update(r0=0,r4=replay.K,r5=replay.K+0x1c4,r8=replay.K,r14=replay.RESUME,r15=sp)
                assert regs==expected_regs,(regs,expected_regs)
                assert len(m.wrapper)==1
                records.append(dict(outer=hex(outer),allowed=allowed,sp=hex(sp),status=hex(m.status_word),
                                    events=[c['hook'] for c in calls],all_14_words_match=True,native_continuation_registers_match=True))
            finally:m.close()
    return records

def disabled():
    records=[]
    replay.NATIVE_SP=0x20465800
    for scenario in ['legacy_handshake','retired_session']:
        m=Machine();m.legacy=scenario=='legacy_handshake'
        try:
            status=m.load()
            if scenario=='legacy_handshake':assert status!=0
            else:
                assert status==0
                m.cpu.write(m.get(replay.RV_ROOT+replay.RO['code_address']),b'\0\0\0\0')
                m.policy['h40']='done'
                m.h40(0x201558a8)
            assert m.cpu.read(replay.RV_ROOT+replay.RO['state'],1)[0]==6
            assert m.get(replay.RV_ROOT+replay.RO['block'])==0 and m.get(replay.RV_ROOT+replay.RO['lease'])==0
            assert m.cpu.read(0x2022f5ac,1)==b'\x07'
            before=len(m.calls)
            for hook in [1,2,5,6,7,8,9,10]:
                regs={f'r{i}':0x11000000+i*0x10101 for i in range(14)}
                regs.update(r12=replay.PARAMS,lr=replay.END,r15=0x20446000)
                at=m.call(replay.SYM[f'rv_hook_{hook:02d}'],regs)
                assert len(m.calls)==before
                if scenario=='retired_session' and hook==7:
                    assert at==replay.END and m.r('r0')==1 and m.get(0x2037f3bc)==0
                else:
                    assert at==replay.SYM[f'rv_resume_{hook:02d}']
                    expected=regs.copy()
                    if hook==1:expected['r0']=0x20271fec
                    if hook==2:expected.update(r2=regs['r0'],r0=5)
                    if hook==5:expected['r2']=0x2023fd38
                    if hook==6:expected['r0']=0x20260000
                    if hook in (7,9):expected['r15']-=4
                    if hook==8:expected['r11']=0x20220000
                    if hook==10:expected['r0']=1
                    for r,v in expected.items():assert m.r(r)==v,(scenario,hook,r,hex(m.r(r)),hex(v))
                records.append(dict(scenario=scenario,hook=hook,dat_calls=0,native_continuation=True))
            calls,regs=m.h40(0x201558a8)
            assert not calls and regs['r0']==0 and regs['r15']==replay.NATIVE_SP
            records.append(dict(scenario=scenario,hook=40,dat_calls=0,native_encoder_called=True))
            assert m.fd is None
            m.call(replay.SYM['rv_load'],dict(r0=replay.RV_ROOT,r1=replay.SYM['rv_trust'],lr=replay.END,r15=0x20446000))
            assert m.r('r0')==0xfffffff5 and len(m.calls)==before,(hex(m.r('r0')),len(m.calls),before)
        finally:m.close()
    return records

def main():
    signal.alarm(600);start=time.monotonic()
    data=dict(classification='linked r7 machine code, declared native and DAT stand-ins',
              arguments=arguments(),disabled=disabled(),bin_sha256=replay.hashlib.sha256(replay.BIN).hexdigest(),
              elapsed_seconds=round(time.monotonic()-start,3),timeout_seconds=600)
    (HERE/'local/machine-boundaries.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(dict(argument_cases=len(data['arguments']),disabled_cases=len(data['disabled']),elapsed_seconds=data['elapsed_seconds'])))
    signal.alarm(0)
if __name__=='__main__':main()
