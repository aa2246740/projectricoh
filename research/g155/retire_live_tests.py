"""在 RPC 返回途中执行本轮 resident 的真实 rv_retire，再继续 DAT 调用。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
from native_support import Camera,H,boot_current,TMP
from boot_tests import prepare,record,watch
from fault_tests import shot_blocked
from image_loader import Elf

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--unit',default='50mm');args=parser.parse_args()
    start=time.monotonic();cam=Camera(args.unit);prepare(cam);cam.put_s(0xfd4,record(cam,number=2))
    trace=watch(cam);work=TMP/'retire-live'/args.unit;work.mkdir(parents=True,exist_ok=True)
    address=0x206d0c00;resume=0x206d0f00;retire=cam.h.symbols['rv_retire']
    lines=['.section .text,"ax"','.global after_rpc','after_rpc:']
    lines += [f'push r{i}' for i in range(14)]+['push lr','mvfc r0,psw','push r0',
        'seth r0,#0x2005','or3 r0,r0,#0x4700','ldi r1,#2',
        f'seth r12,#{retire>>16}',f'or3 r12,r12,#{retire&65535}','jl r12',
        'pop r0','mvtc r0,psw','pop lr']
    lines += [f'pop r{i}' for i in reversed(range(14))]
    lines += [f'seth lr,#{resume>>16}',f'or3 lr,lr,#{resume&65535}','ld lr,@lr','jmp lr']
    source=work/'return.S';source.write_text('\n'.join(lines)+'\n')
    script=work/'return.ld';script.write_text(f'SECTIONS {{ .text {address:#x} : {{ *(.text) }} /DISCARD/ : {{ *(.comment .note* .gnu.attributes) }} }}\n')
    tools=ROOT/'research/tooling_m32r_asm/prefix/bin'
    commands=[[tools/'m32r-elf-as','-m32r','-o',work/'return.o',source],
              [tools/'m32r-elf-ld','--no-undefined','-T',script,'-o',work/'return.elf',work/'return.o']]
    for command in commands:
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True,timeout=1800)
        assert result.returncode==0,result.stdout+result.stderr
    code=next(s['data'] for s in Elf(work/'return.elf').sections if s['name']=='.text');cam.h.b.write(address,code)
    state=dict(W=0,retire_entries=[]);prior=cam.p.rpc.call
    def transport(cmd,value):
        result=prior(cmd,value)
        if cmd==22:
            state['W']+=1
            if state['W']==12:
                b=cam.h.b;original=b.get_reg('r14');b.write(resume,original.to_bytes(4,'big'));b.set_reg('r14',address)
                state['resume']=hex(original)
        return result
    def entered(b):
        state['retire_entries'].append(dict(inflight=cam.h.u(0x20054706,1),W=state['W'],word=cam.h.u(0x200547ec)))
        return False
    cam.h.b.add_breakpoint(retire,entered);cam.p.rpc.call=transport
    answer=boot_current(cam)
    assert answer['root']==6 and answer['word']==14 and state['W']==12,(answer,state)
    assert state['retire_entries'] and state['retire_entries'][0]==dict(inflight=1,W=12,word=6),state
    assert not trace['S'] and not cam.p.files.live
    shot=shot_blocked(cam)
    result=dict(status='PASS',backend=os.environ['GXR_HARNESS_BACKEND'],seconds=time.monotonic()-start,
        unit=args.unit,reply=answer,shot=shot,state=state,return_code_bytes=len(code),return_code_sha256=hashlib.sha256(code).hexdigest(),
        method='RPC 返回经临时返回片段调用真实 resident rv_retire；保存并恢复寄存器、PSW 和 SP。',
        commands=[[str(x) for x in c] for c in commands])
    (HERE/'evidence'/('retire-live-'+args.unit+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
