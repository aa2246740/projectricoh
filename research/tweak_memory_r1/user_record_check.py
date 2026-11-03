"""Recheck old and current user-record bytes from actual UI sessions."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime, TEMP, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',default='user-record-helper')
    options=p.parse_args()
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    rows=[]
    for old,tree,source in [(True,'engine_v63_g154','legacy-user-controls-final.pkl.z'),
            (False,'engine_v67_g155c','finaluser-controls-final.pkl.z')]:
        engine=ROOT/'firmware'/tree
        elf=engine/('candidate/local/full-r13/engine.elf' if old else 'candidate/local/boot-on/engine.elf')
        path=HERE/'local'/source
        r=Runtime(path,options.name+('-old' if old else '-new'),engine,elf)
        try:
            state=r.cpu.snapshot()
            S=r.u(0x200c0dac)
            expected=r.cpu.read(S+0xfd4,40)
            user=r.u(r.at('g.current_user'),1)
            assert user and r.state('source')['applied_user']==2
            assert (expected==bytes(40)) if old else (expected[5]==0x81)
            for backend,Backend in [('c',PB.PythonBackend),('python',PB.PurePythonBackend)]:
                PB.CACHE=TEMP/options.name/tree/backend
                b=Backend()
                for at,raw,writable in state['regions']:b.map(at,raw,writable)
                for key in ['psw',*['r'+str(i) for i in range(16)],'spi','spu','bpc','bbpc','evb']:
                    b.set_reg(key,state['registers'][key])
                b.map(0x10000000,bytes(4096),True)
                before=b.read(S,4096)
                stop=b.call(r.base+r.sym['memory_build'],[0x10000000,r.at('g.current'),r.at('g.tweak'),user],0x7ffffff0,10000)
                actual=b.read(0x10000000,40)
                assert stop.reason=='return' and actual==expected and b.read(S,4096)==before
                rows.append(dict(profile='g154' if old else 'g155c',backend=backend,
                    snapshot=str(path),snapshot_sha256=sha(path.read_bytes()),record=actual.hex(),
                    exact_record_equal=True,complete_S_unchanged=True,steps=stop.steps))
        finally:r.machine.close()
    result=dict(status='PASS',layer='主机模型：实际手动会话快照中的 DAT 机器码 C/Python 复核',rows=rows,native_state_presets=[])
    out=HERE/'evidence'/(options.name+'.json')
    assert not out.exists()
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',rows=len(rows))))


if __name__=='__main__':main()
