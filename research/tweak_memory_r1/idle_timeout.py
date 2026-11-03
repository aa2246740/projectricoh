"""Observe bounded idle intervals from a real completed control page."""
import argparse
import json
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import Runtime, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--chunks',type=int,default=3)
    p.add_argument('--engine',type=Path,default=ROOT/'firmware/engine_v66_g155b')
    p.add_argument('--elf',type=Path)
    a=p.parse_args()
    assert 1<=a.chunks<=3
    out=HERE/'evidence'/(a.name+'.json')
    assert not out.exists()
    engine=a.engine.resolve()
    r=Runtime(a.source,a.name,engine,a.elf or engine/'candidate/local/boot-on/engine.elf')
    signal.alarm(10800)
    result=dict(status='OPEN',layer='声明单元应答下的模拟器自然空闲路径',
        native_state_presets=[],source=str(a.source),source_sha256=sha(a.source.read_bytes()),
        dat_sha256=r.saved['dat_sha256'],engine=str(engine),
        input_events=[],intervals=[])
    started=time.monotonic()
    try:
        result['before']=r.state('before-idle')
        result['before_tick']=r.u(0x200d183c)
        for index in range(a.chunks):
            stop=r.cpu.run(150_000_000)
            state=r.state('idle-'+str(index+1))
            interval=dict(index=index+1,stop=stop.to_dict(),state=state,tick=r.u(0x200d183c),
                snapshot=r.save('interval-'+str(index+1)))
            result['intervals'].append(interval)
            print(json.dumps(dict(name=a.name,interval=index+1,step=r.cpu.steps,
                tick=interval['tick'],state=state['state'],activity=state['activity'],
                stores=len(r.native_settings),stop=stop.reason)),flush=True)
            out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            if stop.reason!='max_steps' or any(x['call']=='native-settings-store' for x in r.native_settings):
                break
        result['after']=r.state('after-idle')
        result['after_tick']=r.u(0x200d183c)
        began_in_menu=result['before']['state']==56 and result['before']['activity']==8
        result['automatic_exit_observed']=bool(began_in_menu and (
            result['after']['state']!=56 or result['after']['activity']!=8))
        result['power_save_path_observed']=bool(r.native_settings)
        result['native_state_changed']=any(result['before'][key]!=result['after'][key]
            for key in ('state','activity'))
        result['record_preserved']=result['after']['record']==result['before']['record']
        result['observation']='COMPLETE'
    except Exception as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc))
    finally:
        signal.alarm(0)
        result.update(native_settings=r.native_settings,events=r.events,
            snapshot=r.save('final'),elapsed_seconds=time.monotonic()-started,
            boundary='Native ticks are reported without equating them to physical camera minutes. No power input is supplied.')
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        r.machine.close()


if __name__=='__main__':
    main()
