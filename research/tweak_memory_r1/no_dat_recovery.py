"""Check both raw shutter requests after a fresh MAIN cold with the DAT removed."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime,load_snapshot,sha,TEMP
from repro_flow import phase


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--settings',type=Path,required=True)
    p.add_argument('--guard-receipt',type=Path,required=True);a=p.parse_args()
    guard=json.loads(a.guard_receipt.read_text());assert guard['status']=='PASS' and guard['guard_state']['word']==14
    rows=[]
    phase('cold_run.py',['--name',a.name,'--unit','mount','--empty-card','--settings-source',a.settings,
        '--budget',250000000,'--timeout',14400],a.name+'-cold-run',rows)
    source=HERE/'local'/(a.name+'-session.pkl.z');observed=[]
    for key,raw in (('HALF',13),('FULL',14)):
        r=Runtime(source,a.name+'-'+key.lower());entries=[];continuations=[]
        try:
            assert r.saved['cold_origin'] and r.saved['dat_path'] is None
            assert r.u(0x200547ec)&12==0
            def entered(cpu):
                pointer=cpu.get_reg('r4')
                if r.u(pointer+12)==raw and r.u(pointer+16)==1:
                    entries.append(r.save('C01-input'))
                return False
            def resumed(cpu):
                if entries:
                    continuations.append(dict(step=cpu.steps,pc=hex(cpu.get_reg('pc')),word=r.u(0x200547ec)))
                    return True
                return False
            r.cpu.add_breakpoint(0x202afe98,entered);r.cpu.add_breakpoint(0x202afe9c,resumed)
            r.panel.set_key(key,True)
            for _ in range(20):
                stop=r.cpu.run(1_000_000)
                if stop.reason=='breakpoint':break
                assert stop.reason=='max_steps',stop
            r.panel.set_key(key,False)
            assert entries and continuations
            captured=ROOT/entries[0]['path'];cpu=load_snapshot(captured)['cpu'];regs=cpu['registers']
            sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
            replays=[]
            for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
                PB.CACHE=TEMP/'no-DAT-recovery'/a.name/backend;b=Backend()
                for at,data,writable in cpu['regions']:b.map(at,data,writable)
                for name in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(name,regs[name])
                S=int.from_bytes(b.read(0x200c0dac,4),'big');before=b.read(S,4096)
                b.add_breakpoint(0x202afe9c,lambda current:True)
                stop=b.call(regs['pc'],[],regs['r14'],20000)
                assert stop.reason=='breakpoint' and stop.pc==0x202afe9c and b.read(S,4096)==before
                replays.append(dict(backend=backend,steps=stop.steps,continuation=hex(stop.pc),S_equal=True))
            observed.append(dict(key=key,raw=raw,input=entries[0],continuations=continuations,replays=replays))
        finally:r.machine.close()
    result=dict(status='PASS',layer='新 MAIN 冷启动及实际 GPIO；C/Python 同一 H52 指令复放',
        no_DAT=True,guard_before=14,new_cold_source_sha256=sha(source.read_bytes()),requests=observed,phases=rows,
        native_state_presets=[],scope='Both requests resume at the original C01 continuation. Complete capture and photos remain OPEN.')
    out=HERE/'evidence'/(a.name+'-result.json');assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',requests=len(observed))))


if __name__=='__main__':main()
