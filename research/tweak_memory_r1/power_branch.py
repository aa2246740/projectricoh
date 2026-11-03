"""Observe each legal readiness result without replacing the body's control flow."""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import ROOT, Runtime, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--result', type=int, choices=(0, 1), required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--budget', type=int, default=20_000_000)
    a = p.parse_args()
    os.environ['GXR_TWEAK_UNIT68_RESULT'] = str(a.result)
    r = Runtime(a.source, a.name, a.engine, a.elf)
    stores = []
    def store(cpu):
        at, length = cpu.get_reg('r4'), cpu.get_reg('r5')
        if length != 4096:
            return False
        data = cpu.read(at, length)
        path = HERE/'local'/(a.name+'-native-store.bin')
        path.write_bytes(data)
        row = dict(step=cpu.steps, path=str(path.relative_to(ROOT)), sha256=sha(data),
            record=data[0xfd4:0xffc].hex(), return_address=hex(cpu.get_reg('lr')))
        stores.append(row)
        def done(c):
            row.update(return_step=c.steps, result=c.get_reg('r0'))
            return True
        cpu.add_breakpoint(cpu.get_reg('lr'), done)
        return False
    r.cpu.add_breakpoint(0x200997cc, store)
    result = dict(status='OPEN', layer='声明单元输入的分支探查', native_state_presets=[],
        source_sha256=sha(a.source.read_bytes()), declared_unit68_result=a.result)
    try:
        result['start'] = r.state('start')
        stop = r.cpu.run(a.budget)
        result['stop'] = stop.to_dict()
        result['final'] = r.state('final')
    finally:
        result.update(stores=stores, native_settings=r.native_settings, snapshot=r.save('final'),
            events=r.events, unit_events=r.machine.devices['startup'].standby_model.events,
            boundary='This probe does not establish the actual unit readiness state or physical NAND retention')
        path = HERE/'evidence'/(a.name+'.json')
        assert not path.exists()
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        r.machine.close()
        print(json.dumps(dict(name=a.name, stores=len(stores), final=result.get('final'), stop=result.get('stop'))))


if __name__ == '__main__':
    main()
