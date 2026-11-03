#!/usr/bin/python3
"""Cold execution with a narrowly declared persistent logical settings source."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import pickle
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import cold_run as C
import panel


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--settings-source',type=Path,required=True)
    parser.add_argument('--expected-target',type=Path)
    parser.add_argument('--mode-notices',action='store_true')
    parser.add_argument('--shutter-during-dirty',action='store_true')
    parser.add_argument('--preview-link',action='store_true')
    parser.add_argument('--word-columns',action='store_true')
    extra,remaining=parser.parse_known_args()
    sys.argv=[sys.argv[0],*remaining]
    name=remaining[remaining.index('--name')+1]
    if extra.mode_notices:
        path=HERE/'emulator/unit_link_copy.py'
        spec=importlib.util.spec_from_file_location('unit_link',path)
        linked=importlib.util.module_from_spec(spec);sys.modules['unit_link']=linked;spec.loader.exec_module(linked)
    preview_proofs=[]
    if extra.preview_link:
        spec=importlib.util.spec_from_file_location('v310_preview_link',HERE/'emulator/preview_link.py')
        linked=importlib.util.module_from_spec(spec);sys.modules[spec.name]=linked;spec.loader.exec_module(linked)
        preview_proofs=[linked.constructor_proof(unit) for unit in ('50mm','28mm','mount')]
        linked.install()
    if extra.word_columns:
        spec=importlib.util.spec_from_file_location('v310_word_nand',HERE/'emulator/nand_word.py')
        word_model=importlib.util.module_from_spec(spec);sys.modules[spec.name]=word_model;spec.loader.exec_module(word_model)
        word_model.install()
    output=HERE/'evidence'/f'{name}-record.json'
    assert not output.exists()
    block=extra.settings_source.read_bytes()
    assert len(block)==4096
    assert int.from_bytes(block[-4:],'big')==sum(struct.unpack('>2046H',block[:0xffc]))&0xffffffff
    spec=importlib.util.spec_from_file_location('v310_storage_copy',HERE/'emulator/storage_copy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    elf=ROOT/'firmware/engine_v66_g155b/candidate/local/boot-on/engine.elf'
    table={}
    for line in subprocess.check_output([str(tool),'-t',str(elf)],text=True).splitlines():
        fields=line.split()
        if len(fields)>=5 and fields[-1] in ('eng_boot_check','boot_run','n','g','ingress'):
            table[fields[-1]]=int(fields[0],16)
    source_events,gate_events=[],[]
    held={};shutter=dict(requested=False,released=False,inputs=[],keys=[],native_state_presets=[])
    OriginalPanel=panel.Panel
    class TransactionPanel(OriginalPanel):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);held['panel']=self
    panel.Panel=TransactionPanel
    class RecordMachine(module.Machine):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            cpu=self.cpu
            def integer(at,n=4):return int.from_bytes(cpu.read(at,n),'big')
            self.integer=integer
            if extra.shutter_during_dirty:
                def fixed_word(at,data):
                    word=integer(0x200547ec)
                    if word==6 and not shutter['requested']:
                        shutter['requested']=True
                        for key in ('HALF','FULL'):held['panel'].set_key(key,True)
                        shutter['inputs'].append(dict(step=cpu.steps,word=word,pressed=True))
                    elif word==2 and shutter['requested'] and not shutter['released']:
                        shutter['released']=True
                        for key in ('FULL','HALF'):held['panel'].set_key(key,False)
                        shutter['inputs'].append(dict(step=cpu.steps,word=word,pressed=False))
                cpu.add_write_trace(0x200547ec,0x200547f0,fixed_word)
                def native_key(c):
                    q=c.get_reg('r4')
                    shutter['keys'].append(dict(step=c.steps,word=integer(0x200547ec),
                        raw=integer(q+12),pressed=integer(q+16)))
                    return False
                cpu.add_breakpoint(0x202afe98,native_key)
                for at,label in ((0x2005296c,'cancel'),(0x202afe9c,'continue')):
                    def key_path(c,label=label):
                        if shutter['keys']:shutter['keys'][-1].update(path=label,end_step=c.steps)
                        return False
                    cpu.add_breakpoint(at,key_path)
            def persistent_read(c):
                lba,count,destination=(c.get_reg('r4'),c.get_reg('r5'),c.get_reg('r6'))
                if (lba,count)!=(0x2b690,8):return False
                assert destination==0x204b0b94
                source_events.append(dict(step=c.steps,lba=lba,sectors=count,destination=hex(destination),
                    source_sha256=hashlib.sha256(block).hexdigest(),origin='记录来源为声明放置，非真实手动保存'))
                c.write(destination,block)
                c.set_reg('r0',0)
                c.set_reg('pc',c.get_reg('lr'))
                return False
            cpu.add_breakpoint(0x2009e8f0,persistent_read)
            installed=set()
            def loaded(address,data):
                code=integer(0x20054770)
                if code<0x20000000 or code>=0x20800000 or code in installed:return
                installed.add(code)
                dat=(ROOT/'firmware/package_v310_g155b_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
                base=code-int.from_bytes(dat[132:136],'big')
                self.dat_base=base
                for key in ('eng_boot_check','boot_run'):
                    pc=base+table[key]
                    def gate(c,key=key):
                        s=integer(0x200c0dac);r=0x20054700
                        row=dict(label=key,step=c.steps,activity=integer(0x205d9bf8),state=integer(0x205d9c00),
                            root_state=integer(r+5,1),inflight=integer(r+6,1),word=integer(r+236),
                            my=integer(0x205d9aa3,1),pending=integer(0x205da00b,1),
                            S=hex(s),S_bytes=integer(0x200c0db0),S_version=c.read(s+14,2).hex(),
                            S_source=integer(s+8,1),selector=integer(s+0x36e,1),
                            wb=c.read(s+0x6dd,2).hex(),record=c.read(s+0xfd4,40).hex(),
                            link=integer(0x2040f804),unit=c.read(0x2040f81c,48).hex(),
                            epochs=[integer(r+8+4*i) for i in range(12)],
                            engine_flags=c.read(base+table['g']+4856,56).hex())
                        if len(gate_events)<100:gate_events.append(row)
                        if key=='eng_boot_check' and len([x for x in gate_events if x['label']==key])==1:
                            state=dict(regions=[(at,bytes(data),writable) for at,data,writable in c.regions],
                                registers={k:c.get_reg(k) for k in [*[f'r{i}' for i in range(16)],'pc','psw']},
                                expected_function=base+table[key],cold_step=c.steps,gate=row.copy())
                            (HERE/'local'/f'{name}-gate-input.z').write_bytes(zlib.compress(pickle.dumps(state,protocol=4),6))
                        ret=c.get_reg('lr');prior=c.breakpoints.get(ret);task=self.task()
                        def returned(current,row=row,prior=prior,ret=ret,task=task):
                            stop=prior(current) if prior else False
                            if self.task()==task and 'result' not in row:
                                row.update(result=current.get_reg('r0'),return_step=current.steps)
                                if current.breakpoints.get(ret) is returned:
                                    if prior:current.add_breakpoint(ret,prior)
                                    else:current.breakpoints.pop(ret,None)
                            return stop
                        c.add_breakpoint(ret,returned)
                        return False
                    cpu.add_breakpoint(pc,gate)
            cpu.add_write_trace(0x20054770,0x20054774,loaded)
        def close(self):
            c=self.cpu;u=self.integer;S=u(0x200c0dac)
            if extra.shutter_during_dirty and shutter['released'] and u(0x200547ec)==2:
                shutter['after_complete']=[]
                for pressed,budget in ((True,1000000),(False,1000000)):
                    held['panel'].set_key('HALF',pressed)
                    stop=c.run(budget)
                    shutter['after_complete'].append(dict(pressed=pressed,step=c.steps,stop=stop.to_dict()))
            result=dict(cold_origin=True,native_state_presets=[],source_events=source_events,
                word_columns=extra.word_columns,preview_model=preview_proofs,
                declared_boundary='logical device 0, LBA 0x2B690, 8 sectors; other reads use the existing model',
                gate_events=gate_events,final_state=u(0x205d9c00),root_state=u(0x20054705,1),
                check_failure=u(0x20054798),fault=u(0x2005475c),word=u(0x200547ec),
                native_activity=u(0x205d9bf8),record=c.read(S+0xfd4,40).hex())
            if extra.shutter_during_dirty:result['shutter_during_real_DIRTY']=shutter
            if hasattr(self,'dat_base'):
                live=c.read(self.dat_base+table['g']+1461,552)
                (HERE/'local'/f'{name}-live.bin').write_bytes(live)
                result['live_sha256']=hashlib.sha256(live).hexdigest()
                if extra.expected_target:
                    result['target_equal']=live==extra.expected_target.read_bytes()
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            try:
                snapshot=c.snapshot();excluded=[]
                for index,device in enumerate(snapshot['devices']):
                    if isinstance(device,dict):
                        for key in list(device):
                            if callable(device[key]):excluded.append([index,key]);del device[key]
                state=dict(cpu=snapshot,excluded_observer_methods=excluded,
                    unit=remaining[remaining.index('--unit')+1],preview_link=extra.preview_link,
                    word_columns=extra.word_columns,source_name=name,
                    body_sha256=hashlib.sha256((ROOT/'firmware/image_v310/local/ilaunch3').read_bytes()).hexdigest())
                path=HERE/'local'/f'{name}-session.pkl.z'
                path.write_bytes(zlib.compress(pickle.dumps(state,protocol=4),3))
                (HERE/'evidence'/f'{name}-snapshot.json').write_text(json.dumps(dict(
                    path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    steps=c.steps,pc=hex(c.get_reg('pc')),excluded_observer_methods=excluded,
                    actual_cold_execution=True,native_state_presets=[]),indent=2)+'\n')
            except Exception as exc:
                (HERE/'evidence'/f'{name}-snapshot-error.json').write_text(json.dumps(dict(
                    type=type(exc).__name__,message=str(exc)))+'\n')
            super().close()
    C.storage_run.Machine=RecordMachine
    C.main()
    if extra.expected_target and not json.loads(output.read_text()).get('target_equal'):
        raise SystemExit(1)


if __name__=='__main__':main()
