"""Prove the narrow accepted native selection using captured real branch inputs."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import load_snapshot,sha,TEMP


def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--name',required=True)
    a=p.parse_args()
    source=HERE/'local'/(a.prefix+'-native-selection.pkl.z')
    saved=load_snapshot(source);state=saved['cpu'];regs=state['registers']
    def mem(at,n):
        for base,data,_ in state['regions']:
            if base<=at and at+n<=base+len(data):return bytes(data[at-base:at-base+n])
        raise ValueError(hex(at))
    S=int.from_bytes(mem(0x200c0dac,4),'big')
    assert regs['pc']==0x202aed3c
    assert int.from_bytes(mem(regs['r8'],4),'big')==int.from_bytes(mem(S+0x2fc,4),'big')==0x8001
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
    rows=[]
    for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
        PB.CACHE=TEMP/'native-selection-proof'/backend
        b=Backend()
        for at,data,writable in state['regions']:b.map(at,data,writable)
        for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,regs[key])
        stores=[];pcs=[]
        b.add_write_trace(0x205d9a7f,0x205d9a80,lambda event:stores.append(dict(field='mode',value=b.read(0x205d9a7f,1).hex())))
        b.add_write_trace(0x205d9aa3,0x205d9aa4,lambda event:stores.append(dict(field='MY',value=b.read(0x205d9aa3,1).hex())))
        for pc in (0x202aedb4,0x2026caac,0x2026a2a4):
            def reached(current,pc=pc):
                pcs.append(dict(pc=hex(pc),r4=current.get_reg('r4')));return False
            b.add_breakpoint(pc,reached)
        b.add_breakpoint(0x202aedd8,lambda current:True)
        stop=b.call(regs['pc'],[],0x7ffffff0,1000)
        assert stop.reason=='breakpoint' and stop.pc==0x202aedd8
        assert stores==[dict(field='MY',value='00'),dict(field='mode',value='00')],stores
        assert b.read(S+0x2fc,4)==b'\0\0\x80\1'
        rows.append(dict(backend=backend,steps=stop.steps,selected_word='0x8001',path=pcs,stores=stores,
            no_declared_native_changes=True,original_selection_word_preserved=True))
    native=ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'
    image=native.read_bytes()
    # Original section 9 is loaded at 0x2025D800; find the mapped section by address.
    import struct
    bindings=[]
    for start,length in ((0x202aed3c,0x9c),(0x2026a2a4,12),(0x202738ac,12)):
        for i in range(16):
            off,base,n,_,_=struct.unpack_from('>5I',image,32+20*i)
            if base<=start and start+length<=base+n:
                raw=image[512+off+start-base:512+off+start-base+length]
                assert mem(start,length)==raw
                (HERE/'local'/(a.name+'-'+hex(start)+'.bin')).write_bytes(raw)
                bindings.append(dict(address=hex(start),bytes=length,sha256=sha(raw),original_equal=True));break
        else:raise ValueError(hex(start))
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',layer='模拟器实际选择输入；C/Python 原厂指令复放',
        source=str(source.relative_to(ROOT)),source_sha256=sha(source.read_bytes()),body_sha256=saved['body_sha256'],
        confirmed_allow_rule=dict(native_selection=0x8001,actual_mode=0,MY=0,pending=0),
        other_selections='Unconfirmed for BOOT and refused by the candidate.',rows=rows,original_bytes=bindings,
        native_state_presets=[],scope='Proves this native selection branch. It does not map every physical dial position.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',rows=len(rows))))


if __name__=='__main__':main()
