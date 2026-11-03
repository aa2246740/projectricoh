"""Recheck the observed native block-store failure with both instruction cores."""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import ROOT, TEMP, Runtime, load_snapshot, sha


def main():
    prior_environment = {key:os.environ.get(key) for key in ('GXR_TWEAK_UNIT68_RESULT', 'GXR_TWEAK_POWER_COMPLETE')}
    os.environ['GXR_TWEAK_UNIT68_RESULT'] = '0'
    os.environ['GXR_TWEAK_POWER_COMPLETE'] = '1'
    source = HERE/'local/b-power-store-0-final.pkl.z'
    engine = ROOT/'firmware/engine_v66_g155b'
    r = Runtime(source, 'store-result-check', engine, engine/'candidate/local/boot-on/engine.elf')
    captured = []
    def before_result(cpu):
        captured.append(dict(snapshot=r.save('before-result'), state=r.state('before-result'),
            result=cpu.get_reg('r0'), native_settings=r.native_settings))
        return True
    r.cpu.add_breakpoint(0x20099838, before_result)
    stop = r.cpu.run(10_000_000)
    assert stop.reason == 'breakpoint' and len(captured) == 1 and captured[0]['result'] == 0xffffffff
    r.machine.close()
    saved = load_snapshot(ROOT/captured[0]['snapshot']['path'])
    state = saved['cpu']
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    rows = []
    for backend, Backend in (('c', PB.PythonBackend), ('python', PB.PurePythonBackend)):
        if backend == 'c':
            assert Backend.native_api == 5
        PB.CACHE = TEMP/'store-result-check'/backend
        b = Backend()
        for base, data, writable in state['regions']:
            b.map(base, data, writable)
        for key in ['psw', *['r'+str(i) for i in range(16)], 'spi', 'spu', 'bpc', 'bbpc', 'evb']:
            b.set_reg(key, state['registers'][key])
        S = int.from_bytes(b.read(0x200c0dac, 4), 'big')
        before = b.read(S, 4096)
        b.add_breakpoint(0x20067c5c, lambda cpu:True)
        end = b.call(state['registers']['pc'], [], 0x7ffffff0, 100)
        assert end.reason == 'breakpoint' and b.get_reg('r0') == 0xffffffff
        assert b.read(S, 4096) == before
        rows.append(dict(backend=backend, stop=end.reason, result=b.get_reg('r0'),
            steps=end.steps, complete_S_unchanged=True, record=before[0xfd4:0xffc].hex()))
    result = dict(status='OPEN', recheck='PASS', layer='真实保存返回点的 C/Python 指令复核',
        source_sha256=sha(source.read_bytes()), actual=captured[0], replays=rows, native_state_presets=[],
        boundary='The observed block layer returned -1. This check verifies native error handling, not a successful NAND save.')
    target = HERE/'evidence/store-result-check.json'
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2)+'\n')
    for key, value in prior_environment.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    print(json.dumps(dict(status='OPEN', recheck='PASS', rows=len(rows))))


if __name__ == '__main__':
    main()
