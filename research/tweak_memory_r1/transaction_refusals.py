"""Use the complete RTOS model for refusals and replay the actual pure-04 gate."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime,load_snapshot,sha,TEMP


def main():
    p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);p.add_argument('--name',required=True);a=p.parse_args()
    source=HERE/'local'/(a.prefix+'-boot_run.pkl.z');engine=ROOT/'firmware/engine_v67_g155c';elf=engine/'candidate/local/boot-on/engine.elf'
    rows=[];helper=None
    cases=['non-pure04','record-bad-crc','record-cross-unit','record-old-DAT','record-unknown-category','record-unknown-version','capture-pure04']
    for case in cases:
        r=Runtime(source,a.name+'-'+case,engine,elf)
        S=r.u(0x200c0dac);record=bytearray(r.cpu.read(S+0xfd4,40));change=None
        try:
            if case=='non-pure04':r.cpu.write(S+0x36e,b'\3');change=dict(address=hex(S+0x36e),value='03')
            elif case!='capture-pure04':
                if case=='record-bad-crc':record[-1]^=1
                else:
                    if case=='record-cross-unit':record[6]=(record[6]+1)%3
                    if case=='record-old-DAT':record[28:36]=b'\0'*8
                    if case=='record-unknown-category':record[5]=0xbf
                    if case=='record-unknown-version':record[4]=0x7f
                    struct.pack_into('>I',record,36,zlib.crc32(record[:36]))
                r.cpu.write(S+0xfd4,record);change=dict(address=hex(S+0xfd4),value=record.hex())
            before=r.cpu.read(S,4096);word=r.u(0x200547ec);writes=[];done=[]
            r.cpu.add_write_trace(S,S+4096,lambda at,data:writes.append(dict(address=hex(at),data=bytes(data).hex())))
            r.cpu.add_write_trace(0x200547ec,0x200547f0,lambda at,data:writes.append(dict(address=hex(at),data=bytes(data).hex())))
            peer=r.machine.devices['startup'].rpc_state
            initial_w=sum(v['cmd']==22 for v in peer.get('log',[]));initial_t=peer.get('t',2)
            if case=='capture-pure04':
                pc=r.base+r.sym['boot_s_valid']
                def capture(cpu):
                    done.append(r.save('gate-input'));return True
                r.cpu.add_breakpoint(pc,capture)
            else:
                task=r.machine.task();ret=r.cpu.get_reg('lr');reply=r.cpu.get_reg('r3')
                def returned(cpu):
                    if r.machine.task()!=task:return False
                    data=cpu.read(reply,32)
                    done.append(dict(result=cpu.get_reg('r0'),reply=data.hex()));return True
                r.cpu.add_breakpoint(ret,returned)
            for _ in range(20):
                stop=r.cpu.run(1_000_000)
                if stop.reason=='breakpoint':break
                assert stop.reason=='max_steps',stop
            assert done and not writes and r.cpu.read(S,4096)==before and r.u(0x200547ec)==word
            assert sum(v['cmd']==22 for v in peer.get('log',[]))==initial_w and peer.get('t',2)==initial_t
            if case=='capture-pure04':helper=ROOT/done[0]['path']
            else:
                end=done[0];reply_raw=bytes.fromhex(end['reply'])
                assert end['result']==1 and int.from_bytes(reply_raw[4:8],'big')==0 and int.from_bytes(reply_raw[-4:],'big')==2,end
                rows.append(dict(case=case,status='PASS',backend='complete original standby RTOS model',declared_change=change,
                    native_state_positive_source=sha(source.read_bytes()),S_equal=True,W_S_T_writes=0,DIRTY_GUARD_stores=0,return_value=end))
        finally:r.machine.close()
    assert helper
    cpu=load_snapshot(helper)['cpu'];regs=cpu['registers'];checks=[]
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
    for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
        for case,value,want in (('ordinary',1,1),('non-pure04',3,0)):
            PB.CACHE=TEMP/'pure04-gate'/a.name/backend;b=Backend()
            for at,data,writable in cpu['regions']:b.map(at,data,writable)
            for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,regs[key])
            S=int.from_bytes(b.read(0x200c0dac,4),'big');b.write(S+0x36e,bytes([value]));before=b.read(S,4096);word=b.read(0x200547ec,4)
            stop=b.call(regs['pc'],[],0x7ffffff0,10000)
            assert stop.reason=='return' and b.get_reg('r0')==want and b.read(S,4096)==before and b.read(0x200547ec,4)==word
            checks.append(dict(backend=backend,case=case,selector=value,result=want,steps=stop.steps,S_equal=True,word_equal=True))
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',dat_sha256=sha((ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT').read_bytes()),
        layer='完整原模拟器事务拒收，实际纯 04 门的 C/Python 指令复放',rows=rows,pure04_gate=checks,
        helper_source=str(helper.relative_to(ROOT)),helper_sha256=sha(helper.read_bytes()),native_state_presets=[],
        boundary='Host-declared negative variants of a real valid BOOT input. This does not test physical mode selection or NAND.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',transactions=len(rows),gate_replays=len(checks))))


if __name__=='__main__':main()
