#!/usr/bin/env python3
"""Pin the native key table, H08 movement calls, H07 close bytes and factory state."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    raw=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    expected=json.loads((HERE/'local/native-contract-expected.json').read_text())
    segments=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)]
    def read(va,n):
        for src,base,size,_,_ in segments:
            if base<=va and va+n<=base+size:return raw[512+src+va-base:512+src+va-base+n]
        raise AssertionError(hex(va))
    assert read(0x201c05e4,20).hex()=='d0c0205ad2c0205a80e0279c82e227d82042f000'
    evidence=HERE/'local/evidence';evidence.mkdir(exist_ok=True)
    for name,start,end in (('native-view-init',0x201c05a8,0x201c0674),('native-view-push',0x201c07e0,0x201c08fc)):
        source=evidence/(name+'.bin');source.write_bytes(read(start,end-start))
        command=[str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+hex(start),str(source)]
        (evidence/(name+'.disasm')).write_text(subprocess.check_output(command,text=True))
        (evidence/(name+'-command.json')).write_text(json.dumps(command,indent=2)+'\n')
    keys={}
    for va in range(0x203764c8,0x20376600,12):
        event,handler,after=struct.unpack('>3I',read(va,12));keys[event]=dict(address=va,handler=handler,after=after)
    assert keys[0x23]['handler']==0x202c2abc and keys[0x29]['after']==0x202bd724
    assert keys[0x1f]['handler']==0x202c2880 and keys[0x20]['handler']==0x202c25b8
    assert read(0x202c27d4,12).hex()==expected['movement_call']
    assert read(0x202c2a9c,12).hex()==expected['movement_call']
    assert read(0x202c2ac0,4).hex()==expected['confirm_prologue'] # native r8 retains the key.
    assert read(0x202871dc,32).hex()==expected['close_prefix']
    state=read(0x2022f71c,32);assert state[0]==5 and state[9]==state[10]==1
    assert read(0x2022f5a8,5).hex()==expected['factory_names']
    result=dict(status='PASS',native_key_table=keys,movement_callers=[0x202c27dc,0x202c2aa4],
                H08_function=0x202bb4bc,confirm_callers=[0x202c2d74,0x202c2d84],
                keep_close_argument='native r4; preserved key native r8; original LR forwarded independently',
                factory_cursor_base=1,factory_rows=7,native_close_hex=read(0x202871dc,32).hex(),
                native_view=dict(part2=0x205a27cc,count_byte=0x205a27d4,array_pointer=0x205a27d8,
                                 array=0x205a279c,stride=8,capacity=2,state_slots=[0x205a27a0,0x205a27a8],
                                 assignment_bytes=read(0x201c05e4,20).hex()),
                factory_state_hex=state.hex(),scope='static official bytes; physical key delivery and camera UI remain untested')
    (HERE/'local/native-contract.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS native contract: movement callers=2 key table pinned factory cursor=1 H07 close bytes pinned')
if __name__=='__main__':main()
