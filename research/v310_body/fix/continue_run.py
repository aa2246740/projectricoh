#!/usr/bin/python3
"""Continue actual cold RAM and device snapshots through physical menu keys."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import signal
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def run(source,name):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP and os.getpriority(os.PRIO_PROCESS,0)>=10
    sys.path.insert(0,str(ROOT/'tools/gxr_emulator_standby'))
    preview=module('v310_preview_link',HERE/'emulator/preview_link.py')
    word=module('v310_word_nand',HERE/'emulator/nand_word.py')
    path=HERE/'local'/f'{source}-session.pkl.z'
    snapshot=pickle.loads(zlib.decompress(path.read_bytes()))
    if snapshot['preview_link']:preview.install()
    if snapshot['word_columns']:word.install()
    storage=module('v310_continued_storage',HERE/'emulator/storage_copy.py')
    import outputs
    outputs.declare_media(TEMP)
    assert snapshot['body_sha256']==hashlib.sha256((ROOT/'firmware/image_v310/local/ilaunch3').read_bytes()).hexdigest()
    machine=storage.Machine(str(TEMP/f'{source}.img'))
    c=machine.cpu;c.restore(snapshot['cpu']);c.set_mode('fast');c.set_batch(True)
    from panel import Panel
    p=Panel(c,machine.devices);p.chain(c)
    start=c.steps;events=[];actions=[];returned=[]
    def u(at,n=4):return int.from_bytes(c.read(at,n),'big')
    def state(label,**fields):
        row=dict(label=label,step=c.steps,state=u(0x205d9c00),activity=u(0x205d9bf8),
            word=u(0x200547ec),root=u(0x20054705,1),rows=u(0x2022f5ac,1),
            cursor=u(0x2022f726,1),cached_cursor=u(0x205a2944,1),labels=hex(u(0x2022f5a8)))
        row.update(fields);events.append(row);return row
    for at,label in ((0x2028709c,'H01'),(0x202870a8,'H02'),(0x2029ebc0,'H50'),(0x202b1310,'H51')):
        prior=c.breakpoints.get(at)
        def hit(cpu,label=label,prior=prior):
            old=prior(cpu) if prior else False;state(label);return old
        c.add_breakpoint(at,hit)
    def constructor(cpu):
        state('native-image-entry');ret=cpu.get_reg('lr');prior=c.breakpoints.get(ret);task=machine.task()
        def end(current):
            old=prior(current) if prior else False
            if machine.task()==task:
                returned.append(state('native-image-return',result=current.get_reg('r0')))
                if prior:current.add_breakpoint(ret,prior)
                else:current.breakpoints.pop(ret,None)
            return old
        cpu.add_breakpoint(ret,end);return False
    c.add_breakpoint(0x20287080,constructor)
    rpc=machine.devices['startup'].rpc_state
    def writes():return sum(x['cmd']==22 for x in rpc.get('log',[]))
    before_w=writes();before_t=rpc.get('t');S=u(0x200c0dac);before_s=c.read(S,4096)
    error=None
    signal.alarm(1800)
    try:
        state('start')
        for key in ['ADJ',*['RIGHT']*4]:
            for down,budget in ((True,400000),(False,20000000)):
                p.set_key(key,down);result=c.run(budget)
                actions.append(dict(key=key,pressed=down,step=c.steps,stop=result.to_dict()))
                state('after-key',key=key,pressed=down)
                if result.reason!='max_steps':raise RuntimeError('native menu continuation stopped: '+result.reason)
            if returned:break
    except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc))
    finally:
        signal.alarm(0)
        final=state('final');after_s=c.read(S,4096)
        out=dict(status='OPEN',source=source,source_snapshot_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_cold_steps=start,steps=c.steps,native_state_presets=[],physical_inputs_only=True,
            events=events,actions=actions,error=error,native_image_returns=returned,
            additional_W_T=writes()-before_w,T_unchanged=rpc.get('t')==before_t,
            changed_S=[i for i,(a,b) in enumerate(zip(before_s,after_s)) if a!=b],
            first_eight_rows=bool(returned and final['rows']==8),
            highlight_verified=False,repeat_apply_verified=False,
            boundary='A constructor return and eight rows still require expected-highlight and no-repeat checks')
        (HERE/'evidence'/f'{name}.json').write_text(json.dumps(out,indent=2)+'\n')
        machine.close()
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    print(json.dumps(run(a.source,a.name)))


if __name__=='__main__':main()
