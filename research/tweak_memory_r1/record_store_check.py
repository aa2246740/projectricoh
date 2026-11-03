"""Check actual op-5 replacement in the full model and its classifier in C/Python."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime,load_snapshot,snapshot_dat,sha,TEMP


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--name',required=True)
    a=p.parse_args();saved=load_snapshot(a.source);regs=saved['cpu']['registers'];dat=snapshot_dat(saved)
    assert (regs['r0'],regs['r1'])==(6,5)
    engine=ROOT/'firmware/engine_v67_g155c';elf=engine/'candidate/local/boot-on/engine.elf'
    rows=[];expected=None;classifier=None;base=None
    for case in ('actual-update','unknown-tail'):
        r=Runtime(a.source,a.name+'-'+case,engine,elf)
        try:
            S=r.u(0x200c0dac);request=r.cpu.read(regs['r2'],64);buffer=int.from_bytes(request[48:52],'big')
            expected=r.cpu.read(buffer+24,40)
            assert expected[:5]==b'GXR2\3' and expected[28:36]==dat[20:28]
            assert zlib.crc32(expected[:36])==int.from_bytes(expected[36:],'big')
            if case=='unknown-tail':r.cpu.write(S+0xfd4,b'UNKN'+bytes(range(36)))
            before=r.cpu.read(S,4096);writes=[];done=[];task=r.machine.task()
            r.cpu.add_write_trace(S,S+4096,lambda at,data:writes.append(dict(address=hex(at),bytes=len(data))))
            def returned(cpu):
                if r.machine.task()!=task:return False
                done.append(cpu.get_reg('r0'));return True
            r.cpu.add_breakpoint(regs['r14'],returned)
            for _ in range(10):
                stop=r.cpu.run(1_000_000)
                if stop.reason=='breakpoint':break
                assert stop.reason=='max_steps',stop
            assert done
            after=r.cpu.read(S,4096);result=done[0]
            assert before[:0xfd4]==after[:0xfd4] and before[0xffc:]==after[0xffc:]
            if case=='actual-update':assert result==0 and after[0xfd4:0xffc]==expected
            else:assert result==0xfffffff9 and before==after and not writes
            rows.append(dict(case=case,backend='complete original standby RTOS model',result=result,
                record_before=before[0xfd4:0xffc].hex(),record_after=after[0xfd4:0xffc].hex(),expected_record=expected.hex(),
                outside_40B_equal=True,neighbor_before=before[0xfc4:0xfd4].hex(),checksum_equal=before[0xffc:]==after[0xffc:],
                writes=writes,declared_change=None if case=='actual-update' else 'Only the existing 40 B record is declared unknown.'))
            classifier=r.sym['owned_record'];base=r.base
        finally:r.machine.close()
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
    checks=[];cpu=saved['cpu']
    for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
        for case,record,want in (('actual-valid',expected,1),('unknown-tail',b'UNKN'+bytes(range(36)),0)):
            PB.CACHE=TEMP/'record-classifier'/a.name/backend;b=Backend()
            for at,data,writable in cpu['regions']:b.map(at,data,writable)
            for key in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(key,regs[key])
            b.map(0x10000000,bytes(4096),True);b.write(0x10000000,record)
            S=int.from_bytes(b.read(0x200c0dac,4),'big');before=b.read(S,4096)
            stop=b.call(base+classifier,[0x10000000],0x7ffffff0,200000)
            assert stop.reason=='return' and b.get_reg('r0')==want and b.read(S,4096)==before
            checks.append(dict(backend=backend,case=case,result=want,steps=stop.steps,S_equal=True))
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',layer='完整原模拟器实际 op 5；记录分类器的 C/Python 指令复放',
        dat_sha256=sha(dat),source_sha256=sha(a.source.read_bytes()),rows=rows,classifier_checks=checks,native_state_presets=[],
        boundary='RAM replacement with actual RTOS context. The classifier replay does not replace a complete Python RTOS run or prove NAND persistence.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',transactions=len(rows),classifier_replays=len(checks))))


if __name__=='__main__':main()
