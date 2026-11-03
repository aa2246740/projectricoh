#!/usr/bin/python3
"""Compare the seven linked native bridges at their declared call boundary."""
import hashlib
import json
from pathlib import Path
import signal
import struct
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/gxr_emulator_batch'))
from backend import Backend

def elf_symbols(path):
    raw=path.read_bytes()
    assert raw[:6]==b'\x7fELF\x01\x02'
    off=struct.unpack_from('>I',raw,32)[0]
    width,count=struct.unpack_from('>HH',raw,46)
    sections=[struct.unpack_from('>10I',raw,off+i*width) for i in range(count)]
    result={}
    for sec in sections:
        if sec[1]!=2:continue
        names=sections[sec[6]];strings=raw[names[4]:names[4]+names[5]]
        for p in range(sec[4],sec[4]+sec[5],sec[9]):
            name,value,size,info,other,index=struct.unpack_from('>IIIBBH',raw,p)
            text=strings[name:strings.find(b'\0',name)].decode()
            if text:result[text]=value
    return result

def replay(variant,name,target,seed,psw):
    folder=HERE/'local/rebuild/v'/variant/'build'
    symbols=elf_symbols(folder/'resident.elf')
    cpu=Backend(mode='fast',trace_limit=128)
    try:
        cpu.map(0x20000000,bytes(0x800000));cpu.write(0x2005276c,(folder/'resident.bin').read_bytes())
        cpu.set_reg('psw',psw);cpu.set_reg('cbr',psw&1)
        cpu.set_reg('spu',0x20440000);cpu.set_reg('spi',0x20430000)
        for i in range(14):cpu.set_reg(f'r{i}',(0x1020304*(i+1)^seed)&0xffffffff)
        cpu.set_reg('r15',0x20440000);cpu.set_reg('lr',0x20051000)
        expected=[cpu.get_reg(f'r{i}') for i in range(14)]
        cpu.set_reg('pc',symbols[name]);cpu.add_breakpoint(target,lambda c:True)
        reached=cpu.run(256)
        assert cpu.get_reg('pc')==target,(variant,name,reached.to_dict())
        entry=[cpu.get_reg(f'r{i}') for i in range(14)]
        assert entry[0]==target and entry[4:8]==expected[:4]
        assert entry[8:14]==expected[8:14]
        assert cpu.get_reg('r15')==0x20440000-28
        boundary={'registers':entry,'sp':cpu.get_reg('r15'),'psw':cpu.get_reg('psw'),'cbr':cpu.get_reg('cbr')}
        return_pc=cpu.get_reg('lr');cpu.breakpoints.clear()
        for i in range(14):cpu.set_reg(f'r{i}',(0xe0000000+i*0x10101+seed)&0xffffffff)
        cpu.set_reg('cbr',(psw&1)^1);cpu.set_reg('pc',return_pc)
        cpu.add_breakpoint(0x20051000,lambda c:True);done=cpu.run(256)
        assert cpu.get_reg('pc')==0x20051000,(variant,name,done.to_dict())
        final={reg:cpu.get_reg(reg) for reg in [*[f'r{i}' for i in range(16)],'psw','cbr']}
        assert [final[f'r{i}'] for i in range(8,14)]==expected[8:14]
        assert final['r14']==0x20051000 and final['r15']==0x20440000
        return {'entry':boundary,'return':final,'steps':cpu.steps}
    finally:
        cpu.close()

def main():
    signal.alarm(600);start=time.monotonic();cases=[]
    names=['open','read','close','alloc','free','sd_id','layer']
    targets=[0x200a40b4,0x200a449c,0x200a437c,0x2005bf5c,0x2005c038,0x200a3240,0x201c092c]
    for name,target in zip(names,targets):
        for seed in [0,0xdeadbeef,0xffffffff,0x80000000]:
            for psw in [0x80,0x81,0xc0,0xc1]:
                old=replay('r2','rv_native_'+name,target,seed,psw)
                new=replay('r3','rv_native_'+name,target,seed,psw)
                assert old['entry']==new['entry'] and old['return']==new['return'],(name,old,new)
                cases.append({'name':name,'target':hex(target),'seed':hex(seed),'psw':hex(psw),
                              'old_steps':old['steps'],'new_steps':new['steps'],'equal':True})
    result={'classification':'linked M32R bridges with a declared native callee substitute',
            'cases':cases,'comparisons':len(cases),'runs':2*len(cases),
            'elapsed_seconds':round(time.monotonic()-start,3),'timeout_seconds':600,
            'hashes':{v:hashlib.sha256((HERE/f'local/rebuild/v/{v}/build/resident.bin').read_bytes()).hexdigest() for v in ['r2','r3']},
            'library_sha256':hashlib.sha256((ROOT/'tools/gxr_emulator_batch/build/libgxr_m32r.dylib').read_bytes()).hexdigest(),
            'limits':['The actual stock native functions and camera hardware are not executed.',
                      'The internal callee return address differs because the two bridges link at different locations.']}
    (HERE/'local/native-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));signal.alarm(0)

if __name__=='__main__':main()
