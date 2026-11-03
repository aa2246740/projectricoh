"""Exercise final DAT compensation failure with declared unit W error replies."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime,load_snapshot,sha,TEMP


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--name',required=True)
    a=p.parse_args();engine=ROOT/'firmware/engine_v67_g155c'
    r=Runtime(a.source,a.name,engine,engine/'candidate/local/boot-on/engine.elf')
    import unit_peer
    original=unit_peer.call;failures=[];keys=[]
    def declared_error(state,command,value,unit='50mm'):
        answer=original(state,command,value,unit)
        if command==22:
            failures.append(dict(step=r.cpu.steps,command=command,value=value,
                successful_peer_value=answer,declared_result=-1))
            return -1
        return answer
    unit_peer.call=declared_error
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    result=dict(status='OPEN',dat_sha256=r.saved['dat_sha256'],source_sha256=sha(a.source.read_bytes()),
        layer='模拟器原始 DAT 指令，声明单元 W 错误应答',native_state_presets=[],declared_errors=failures)
    try:
        def completed(cpu):return r.u(0x200547ec)==14
        r.cpu.add_breakpoint(0x202b1210,completed)
        for _ in range(12):
            stop=r.cpu.run(10_000_000)
            if stop.reason=='breakpoint':break
            assert stop.reason=='max_steps',stop
        assert r.u(0x200547ec)==14 and len(failures)>=2,(r.state('guard'),failures)
        result['guard_state']=r.state('guard-established');result['guard_snapshot']=r.save('guard-established')
        r.cpu.breakpoints.pop(0x202b1210,None)
        def key_entry(cpu):
            pointer=cpu.get_reg('r4')
            row=dict(raw=r.u(pointer+12),pressed=r.u(pointer+16),word=r.u(0x200547ec),step=cpu.steps)
            row['snapshot']=r.save('C01-'+str(len(keys)+1));keys.append(row)
            return False
        r.cpu.add_breakpoint(0x202afe98,key_entry)
        for key in ('HALF','FULL','HALF','FULL'):
            r.panel.set_key(key,True);r.run(1_000_000)
            r.panel.set_key(key,False);r.run(1_000_000)
        assert {13,14}<={v['raw'] for v in keys if v['pressed']==1 and v['word']==14},keys
        sys.path.insert(0,str(ROOT/'tools/native_harness_c'));import python_backend as PB
        replays=[]
        for row in keys:
            if row['raw'] not in (13,14) or row['pressed']!=1:continue
            source=ROOT/row['snapshot']['path'];cpu=load_snapshot(source)['cpu'];regs=cpu['registers']
            for backend,Backend in (('c',PB.PythonBackend),('python',PB.PurePythonBackend)):
                PB.CACHE=TEMP/'final-h52'/a.name/backend;b=Backend()
                for at,data,writable in cpu['regions']:b.map(at,data,writable)
                for name in ('psw','spi','spu','bpc','bbpc','evb',*[f'r{i}' for i in range(16)]):b.set_reg(name,regs[name])
                S=int.from_bytes(b.read(0x200c0dac,4),'big');before=b.read(S,4096)
                stop=b.call(regs['pc'],[],regs['r14'],20000)
                assert stop.reason=='return' and b.get_reg('r0')==0 and b.read(S,4096)==before
                replays.append(dict(backend=backend,raw=row['raw'],result=0,steps=stop.steps,S_equal=True))
        result.update(status='PASS',keys=keys,H52_instruction_replays=replays,
            source_DAT_code_changed=False,final=r.state('after-keys'))
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        unit_peer.call=original
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');r.machine.close()
    print(json.dumps(dict(status=result['status'],errors=len(failures),keys=len(keys))))


if __name__=='__main__':main()
