"""Retain an actual pre-write stop and compare C/Python at the same device limit."""
import argparse
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import ROOT, TEMP, Runtime, load_snapshot, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--input', choices=('half', 'power'), default='half')
    a = p.parse_args()
    r = Runtime(a.source, a.name, a.engine, a.elf)
    captured = []
    def before_word(cpu):
        peer = r.machine.devices['startup']
        words = [peer.regs.get(0xf0260060+4*i, 0) for i in range(8)]
        if words[2] != (0x001f0003 if a.input == 'half' else 0x00440000):
            return False
        captured.append(dict(snapshot=r.save('before-word'), words=words, state=r.state('before-device-word')))
        return True
    r.cpu.add_breakpoint(0x20074028, before_word)
    if a.input == 'half':
        r.panel.set_key('HALF', True)
        stop = r.cpu.run(400000)
        r.panel.set_key('HALF', False)
    else:
        r.machine.devices['serial'].input_bytes[8] = (15, 6)
        stop = r.cpu.run(1_000_000)
        r.machine.devices['serial'].input_bytes[8] = (15, 7)
    for _ in range(8):
        if captured:
            break
        stop = r.cpu.run(5_000_000)
        if stop.reason not in ('max_steps', 'breakpoint'):
            raise RuntimeError(str(stop.to_dict()))
    assert captured and stop.reason == 'breakpoint'
    r.machine.close()
    source = ROOT/captured[0]['snapshot']['path']
    saved = load_snapshot(source)
    state, regs = saved['cpu'], saved['cpu']['registers']
    device = next(d for t, d in zip(state['device_types'], state['devices']) if t == 'StartupRegisters')
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    from peripherals import StartupRegisters
    rows = []
    for backend, Backend in (('c', PB.PythonBackend), ('python', PB.PurePythonBackend)):
        if backend == 'c':
            assert Backend.native_api == 5
        PB.CACHE = TEMP/'half-check'/a.name/backend
        b = Backend()
        for at, data, writable in state['regions']:
            b.map(at, data, writable)
        b.set_reg('psw', regs['psw'])
        for i in range(16):
            b.set_reg('r'+str(i), regs['r'+str(i)])
        for key in ('spi', 'spu', 'bpc', 'bbpc', 'evb'):
            b.set_reg(key, regs[key])
        peer = StartupRegisters()
        peer.restore(copy.deepcopy(device))
        peer.backend = type('Clock', (), dict(steps=state['steps']))()
        calls = []
        def write(address, data):
            calls.append(dict(address=hex(address), data=bytes(data).hex()))
            try:
                peer.write(address, data)
            except Exception as exc:
                raise PB.Fault(str(exc))
        b.add_mmio(0xf0260018, 0xf026001c, None, write)
        S = int.from_bytes(b.read(0x200c0dac, 4), 'big')
        before = b.read(S, 4096)
        outcome = b.call(regs['pc'], [], regs['r14'], 10)
        assert outcome.reason == 'fault' and 'HSP transmit requires a declared packet response' in outcome.detail
        assert len(calls) == 1 and b.read(S, 4096) == before
        rows.append(dict(backend=backend, pc=hex(outcome.pc), reason=outcome.reason, detail=outcome.detail,
            writes=calls, settings_equal=True, record=before[0xfd4:0xffc].hex()))
    assert rows[0]['writes'] == rows[1]['writes'] and rows[0]['detail'] == rows[1]['detail']
    result = dict(status='OPEN', recheck='PASS', layer='实测前一条指令快照的 C/Python 主机复核',
        source_sha256=sha(a.source.read_bytes()), actual_stop=captured[0], replays=rows,
        native_state_presets=[], input=a.input,
        boundary='Original short unit request has no declared reply; the complete later device flow remains OPEN')
    path = HERE/'evidence'/(a.name+'.json')
    assert not path.exists()
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(name=a.name, status='OPEN', recheck='PASS', state=captured[0]['state']['state'])))


if __name__ == '__main__':
    main()
