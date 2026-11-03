#!/usr/bin/python3
"""Observe native settings sources and optional resident-word key checks after a cold run."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cold_run as C
import panel


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--scenario',choices=('trace','shutter','cycle','power'),default='trace')
    parser.add_argument('--mode-notices',action='store_true')
    extra,remaining=parser.parse_known_args()
    sys.argv=[sys.argv[0],*remaining]
    name=remaining[remaining.index('--name')+1]
    if extra.mode_notices:
        path=HERE/'emulator/unit_link_copy.py'
        spec=importlib.util.spec_from_file_location('unit_link',path)
        linked=importlib.util.module_from_spec(spec);sys.modules['unit_link']=linked;spec.loader.exec_module(linked)
    output=HERE/'evidence'/f'{name}-source.json'
    assert not output.exists()
    rows,states,keys,words=[],[],[],[]
    hook_counts={50:0,51:0,'load':0}
    held={}
    phase={'name':'cold'}
    Base=C.storage_run.Machine
    Panel=panel.Panel
    class SessionPanel(Panel):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            held['panel']=self
    panel.Panel=SessionPanel

    class SourceMachine(Base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            cpu=self.cpu
            def integer(at,n=4):
                return int.from_bytes(cpu.read(at,n),'big')
            self.integer=integer
            def fixed_word(address,data):
                words.append(dict(step=cpu.steps,word=integer(0x200547ec),phase=phase['name']))
            cpu.add_write_trace(0x200547ec,0x200547f0,fixed_word)
            for at,label in ((0x2029ebc0,50),(0x202b1310,51),(0x200535ec,'load')):
                prior=cpu.breakpoints.get(at)
                def observed(current,label=label,prior=prior):
                    before=prior(current) if prior else False
                    hook_counts[label]+=1
                    return before
                cpu.add_breakpoint(at,observed)
            for address,label in ((0x20099764,'S-storage-read'),(0x2009ac58,'logical-read'),
                    (0x2009e8f0,'NAND-logical-read'),(0x2009e0dc,'NAND-mapping-read'),
                    (0x20067074,'S-native-default'),(0x20067bb4,'S-native-save'),
                    (0x200997cc,'S-storage-write'),(0x2028709c,'H01-word')):
                previous=cpu.breakpoints.get(address)
                def hit(current,address=address,label=label,previous=previous):
                    old=previous(current) if previous else False
                    regs=[current.get_reg(f'r{i}') for i in range(4,8)]
                    row=dict(label=label,step=current.steps,args=regs,task=self.task(),phase=phase['name'])
                    if len(rows)<400:
                        rows.append(row)
                    if label in ('S-storage-read','S-native-save','S-storage-write') or (label=='logical-read' and regs[1]==0x2b690):
                        ret=current.get_reg('lr')
                        task=self.task()
                        before=current.breakpoints.get(ret)
                        def returned(c,row=row,ret=ret,task=task,before=before):
                            stop=before(c) if before else False
                            if self.task()==task and 'return_step' not in row:
                                row.update(return_step=c.steps,result=c.get_reg('r0'))
                                pointer=integer(0x200c0dac)
                                row['record']=c.read(pointer+0xfd4,40).hex()
                                row['s_sha256']=hashlib.sha256(c.read(pointer,4096)).hexdigest()
                            return stop
                        current.add_breakpoint(ret,returned)
                    return old
                cpu.add_breakpoint(address,hit)
            def state(at,data):
                current=integer(0x205d9c00)
                if not states or states[-1]['state']!=current:
                    states.append(dict(state=current,step=cpu.steps,my=integer(0x205d9aa3,1),
                        pending=integer(0x205da00b,1),native_type=integer(0x2022f71c,1),
                        descriptors=hex(integer(0x2022f720)),word=integer(0x200547ec)))
            cpu.add_write_trace(0x205d9c00,0x205d9c04,state)
            address=0x202afe98
            previous=cpu.breakpoints.get(address)
            def key(c):
                stop=previous(c) if previous else False
                message=c.get_reg('r4')
                if 0x20000000<=message<=0x20700000-20:
                    data=c.read(message,20)
                    keys.append(dict(step=c.steps,phase=phase['name'],word=integer(0x200547ec),
                        message=data.hex(),kind=int.from_bytes(data[6:8],'big'),
                        raw=int.from_bytes(data[12:16],'big'),pressed=int.from_bytes(data[16:20],'big')))
                return stop
            cpu.add_breakpoint(address,key)
            for address,label in ((0x2005296c,'cancel'),(0x202afe9c,'continue')):
                def reached(c,label=label):
                    if keys and phase['name']!='cold':
                        keys[-1].update(path=label,result=c.get_reg('r0'),end_step=c.steps)
                    return label=='continue' and phase['name']=='clear-word'
                cpu.add_breakpoint(address,reached)

        def close(self):
            cpu=self.cpu
            integer=self.integer
            presets=[]
            continuations=[]
            try:
                if integer(0x205d9c00)==5 and extra.scenario=='shutter':
                    original=integer(0x200547ec)
                    p=held['panel']
                    # Only the resident's own fixed word is changed in this separate key check.
                    # This does not claim a DAT colour transaction occurred.
                    for flag,label in ((4,'DIRTY'),(8,'GUARD')):
                        phase['name']=label+'-word-fixture'
                        cpu.write(0x200547ec,(original|flag).to_bytes(4,'big'))
                        presets.append(dict(address='0x200547ec',before=original,after=original|flag,
                            purpose='separate resident-word key check; no native state fields changed'))
                        for key in ('HALF','FULL'):
                            for down,budget in ((True,400_000),(False,700_000)):
                                p.set_key(key,down)
                                stop=cpu.run(budget)
                                continuations.append(dict(key=key,pressed=down,step=cpu.steps,stop=stop.to_dict()))
                                if stop.reason!='max_steps':
                                    raise RuntimeError('key continuation stopped: '+stop.reason)
                    cpu.write(0x200547ec,original.to_bytes(4,'big'))
                    phase['name']='clear-word'
                    p.set_key('HALF',True)
                    stop=cpu.run(5_000_000)
                    continuations.append(dict(key='HALF',pressed=True,step=cpu.steps,stop=stop.to_dict()))
                    p.set_key('HALF',False)
                elif integer(0x205d9c00)==5 and extra.scenario=='cycle':
                    from dial import set_dial
                    for code in (5,2):
                        phase['name']='dial-'+str(code)
                        device=set_dial(cpu,self.devices,code)
                        stop=cpu.run(15_000_000)
                        continuations.append(dict(input=device,step=cpu.steps,stop=stop.to_dict()))
                        if stop.reason!='max_steps':
                            break
                elif integer(0x205d9c00)==5 and extra.scenario=='power':
                    serial=self.devices['serial']
                    for level,budget in ((6,1_000_000),(7,100_000_000)):
                        phase['name']='power-input-'+str(level)
                        serial.input_bytes[8]=(15,level)
                        stop=cpu.run(budget)
                        continuations.append(dict(serial_input8=level,step=cpu.steps,stop=stop.to_dict()))
                        if stop.reason!='max_steps':
                            break
            except Exception as exc:
                continuations.append(dict(error=type(exc).__name__,message=str(exc)))
            finally:
                result=dict(cold_origin=True,native_state_presets=[],resident_word_fixtures=presets,
                    scenario=extra.scenario,declared_mode_notices=extra.mode_notices,native_source_calls=rows,states=states,keys=keys,
                    fixed_word_changes=words,hook_counts=hook_counts,
                    continuations=continuations,final_state=integer(0x205d9c00),
                    final_word=integer(0x200547ec),final_my=integer(0x205d9aa3,1),
                    final_pending=integer(0x205da00b,1),steps=cpu.steps,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
                output.write_text(json.dumps(result,indent=2)+'\n')
                (HERE/'local'/f'{name}-final-nand.json').write_text(json.dumps({str(k):bytes(v).hex() for k,v in sorted(self.devices['nand'].pages.items())})+'\n')
                super().close()
    C.storage_run.Machine=SourceMachine
    C.main()


if __name__=='__main__':
    main()
