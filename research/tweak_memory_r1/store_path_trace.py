"""Locate the original block-store error without changing its return values."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from runtime import Runtime, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='store-path-trace')
    parser.add_argument('--source',type=Path,default=HERE/'local/b-power-store-0-final.pkl.z')
    options=parser.parse_args()
    name = options.name
    path = HERE/'evidence'/(name+'.json')
    assert not path.exists()
    os.environ['GXR_TWEAK_UNIT68_RESULT'] = '0'
    os.environ['GXR_TWEAK_POWER_COMPLETE'] = '1'
    source = options.source
    engine = ROOT/'firmware/engine_v66_g155b'
    r = Runtime(source, name, engine, engine/'candidate/local/boot-on/engine.elf')
    rows = []
    for at in (0x200997cc,0x2009ac80,0x2009eb04,0x2009b6bc,0x2009f404,0x2009f67c):
        def entered(cpu, at=at):
            row = dict(function=hex(at),step=cpu.steps,task=r.machine.task(),
                args=[cpu.get_reg('r'+str(i)) for i in range(4,8)])
            rows.append(row)
            ret, task = cpu.get_reg('lr'), r.machine.task()
            prior = cpu.breakpoints.get(ret)
            def returned(c):
                old = prior(c) if prior else False
                if 'return_step' not in row and r.machine.task() == task:
                    row.update(return_step=c.steps,result=c.get_reg('r0'))
                    if at == 0x2009b6bc and not any('error_snapshot' in x for x in rows):
                        row['error_snapshot'] = r.save('first-driver-result')
                    if at == 0x200997cc:
                        return True
                return old
            cpu.add_breakpoint(ret,returned)
            return False
        r.cpu.add_breakpoint(at,entered)
    result = dict(status='OPEN',layer='声明单元应答下的原厂存储指令实测',
        native_state_presets=[],source=str(source),source_sha256=sha(source.read_bytes()))
    try:
        result['before'] = r.state('before')
        stop = r.cpu.run(5_000_000)
        result['stop'] = stop.to_dict()
        result['after'] = r.state('after')
        result['observation'] = 'COMPLETE' if rows and 'result' in rows[0] else 'OPEN'
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__,message=str(exc))
    finally:
        result.update(rows=rows,native_settings=r.native_settings,snapshot=r.save('final'),
            boundary='No logical write or NAND result is replaced. A store error remains OPEN.')
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        r.machine.close()
        print(json.dumps(dict(observation=result.get('observation'),rows=rows)),flush=True)


if __name__ == '__main__':
    main()
