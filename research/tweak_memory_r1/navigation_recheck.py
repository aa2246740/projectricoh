"""Retain a real cursor store and replay that instruction with C and Python."""
import json
from pathlib import Path
import pickle
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime, TEMP, sha


def main():
    name='navigation-recheck'
    out=HERE/'evidence'/(name+'.json')
    assert not out.exists()
    engine=ROOT/'firmware/engine_v67_g155c'
    elf=HERE/'local/p1-before/boot-on/engine.elf'
    source=HERE/'local/g155c-28mm-builtin-r2-choose-navigation-1.pkl.z'
    r=Runtime(source,name,engine,elf)
    sites=[]
    def cursor(at,data):
        if at!=0x2022f726 or bytes(data)!=b'\x02':return
        S=r.u(0x200c0dac)
        if r.u(r.at('n.ui.screen'),1)==0 and r.u(r.at('n.ui.physical'),1)==2 and r.cpu.read(S+0xfd9,2)==b'\x03\x01':
            sites.append(dict(pc=r.cpu._pc,register_pc=r.cpu.get_reg('pc'),step=r.cpu.steps,state=r.state('cursor-store')))
    r.cpu.add_write_trace(0x2022f726,0x2022f727,cursor)
    result=dict(status='OPEN',layer='模拟器导航与同一原生写指令复核',source=str(source),
        source_sha256=sha(source.read_bytes()),native_state_presets=[])
    checkpoint=None
    try:
        r.panel.set_key('UP',True)
        r.run(400_000)
        r.panel.set_key('UP',False)
        for index in range(44):
            checkpoint=r.cpu.snapshot()
            r.run(5_000_000)
            if sites:break
        result['sites']=sites
        if not sites:
            result['observation']='NOT_REPRODUCED'
            result['snapshot']=r.save('final')
        else:
            result['observed']=r.save('observed')
            for device in checkpoint['devices']:
                if isinstance(device,dict):
                    for key in list(device):
                        if callable(device[key]):del device[key]
            retained=dict(r.saved,cpu=checkpoint,native_state_presets=[])
            path=HERE/'local'/(name+'-prior.pkl.z')
            path.write_bytes(zlib.compress(pickle.dumps(retained,protocol=4),3))
            result['prior']=str(path)
    finally:r.machine.close()
    if not sites:
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    second=Runtime(Path(result['prior']),name+'-short',engine,elf)
    captured=[]
    def before(cpu):
        if second.u(0x2022f726,1)==3 and second.u(second.at('n.ui.physical'),1)==2:
            captured.append(second.save('before-store'))
            return True
        return False
    second.cpu.add_breakpoint(sites[0]['pc'],before)
    try:
        stop=second.cpu.run(6_000_000)
        assert stop.reason=='breakpoint' and captured
        state=second.cpu.snapshot()
        physical=second.at('n.ui.physical')
    except BaseException as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc))
        result['short_stop']=second.save('stopped')
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        raise
    finally:second.machine.close()
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    checks=[]
    for backend,Backend in [('c',PB.PythonBackend),('python',PB.PurePythonBackend)]:
        PB.CACHE=TEMP/name/backend
        b=Backend()
        for at,raw,writable in state['regions']:b.map(at,raw,writable)
        for key in ['psw',*['r'+str(i) for i in range(16)],'spi','spu','bpc','bbpc','evb']:
            b.set_reg(key,state['registers'][key])
        S=int.from_bytes(b.read(0x200c0dac,4),'big')
        prior=b.read(S,4096)
        stop=b.call(state['registers']['pc'],[],state['registers']['r14'],1)
        native=int.from_bytes(b.read(0x2022f726,1),'big')
        logical=int.from_bytes(b.read(physical,1),'big')+1
        assert native==2 and logical==3 and b.read(S,4096)==prior
        checks.append(dict(backend=backend,pc=hex(state['registers']['pc']),steps=stop.steps,
            native_cursor=native,DAT_expected_cursor=logical,complete_S_unchanged=True))
    result.update(observation='REPRODUCED',recheck='PASS',before_store=captured[0],checks=checks,
        scope='The actual cursor store differs from the DAT physical row. The reason and full Python UI sequence are separate.')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(observation=result['observation'],recheck='PASS')))


if __name__=='__main__':main()
