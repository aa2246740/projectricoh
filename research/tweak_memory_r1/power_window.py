"""Observe a physical power request during a real nonzero control change."""
import argparse
import json
from pathlib import Path
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import Runtime, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--stage', choices=('before-writes', 'before-preview', 'after-preview'), required=True)
    p.add_argument('--budget', type=int, default=140_000_000)
    a = p.parse_args()
    out = HERE/'evidence'/(a.name+'.json')
    assert not out.exists()
    r = Runtime(a.source, a.name, a.engine, a.elf)
    signal.alarm(7200)
    result = dict(status='OPEN', layer='模拟器实测', native_state_presets=[],
        source=str(a.source), source_sha256=sha(a.source.read_bytes()), stage=a.stage,
        runner_sha256=sha(Path(__file__).read_bytes()),
        boundary='A serial power input is external. Native storage and unit limits remain explicit.')
    services, record_writes = [], []
    cut = []
    started = time.monotonic()
    S = r.u(0x200c0dac)
    r.cpu.add_write_trace(S+0xfd4, S+0xffc, lambda at, data: record_writes.append(dict(
        step=r.cpu.steps, at=hex(at), pc=hex(r.cpu.get_reg('pc')), data=bytes(data).hex())))
    def mark(cpu):
        settings = cpu.read(S,4096)
        settings_path = HERE/'local'/(a.name+'-cut-S.bin')
        settings_path.write_bytes(settings)
        staging_path = HERE/'local'/(a.name+'-cut-staging.bin')
        staging_path.write_bytes(cpu.read(r.at('g.staging'),552))
        cut.append(dict(step=cpu.steps, state=r.state('cut'),
            settings_path=str(settings_path),settings_sha256=sha(settings),
            staging_path=str(staging_path),
            live_sha256=sha(cpu.read(r.at('g.live'),552)),
            staging_sha256=sha(cpu.read(r.at('g.staging'),552)),
            engine_flags={key:r.u(r.at('g.'+key),1) for key in
                ('memory_dirty','memory_want','settings_pending','s_unwritten','uncertain','write_started')}))
        result['cut_snapshot'] = r.save('cut')
        return True
    def service(cpu):
        # The DAT is built by GCC: arguments start at r0. Stock routines
        # use a different calling convention, with arguments at r4.
        sid, op = cpu.get_reg('r1'), cpu.get_reg('r2')
        if sid in (5, 6):
            services.append(dict(step=cpu.steps, id=sid, op=op, task=r.machine.task()))
        if cut:
            return False
        wanted = (a.stage == 'before-preview' and (sid,op) == (5,1)) or (
            a.stage == 'before-writes' and (sid,op) == (6,1))
        if wanted:
            return mark(cpu)
        if a.stage == 'after-preview' and (sid,op) == (5,1):
            ret, task = cpu.get_reg('lr'), r.machine.task()
            prior = cpu.breakpoints.get(ret)
            def returned(c):
                old = prior(c) if prior else False
                if not cut and r.machine.task() == task:
                    return mark(c)
                return old
            cpu.add_breakpoint(ret, returned)
        return False
    assert 'core_call' in r.sym
    r.cpu.add_breakpoint(r.base+r.sym['core_call'], service)
    try:
        result['before'] = r.state('before')
        assert result['before']['screen'] == 3
        r.inputs.append(r.panel.set_key('UP', True))
        stop = r.cpu.run(400_000)
        r.inputs.append(r.panel.set_key('UP', False))
        for index in range(36):
            if cut:
                break
            stop = r.cpu.run(5_000_000)
            if index and index % 4 == 0:
                print(json.dumps(dict(name=a.name, step=r.cpu.steps, services=len(services),
                    pending=len(r.pending), state=r.state('await-stage'))), flush=True)
            if index in (7,15) and not services and not r.pending:
                r.inputs.append(r.panel.set_key('UP', True))
                r.cpu.run(2_000_000)
                r.inputs.append(r.panel.set_key('UP', False))
            if stop.reason != 'max_steps' and not cut:
                raise RuntimeError(str(stop.to_dict()))
        assert cut, 'requested transaction stage did not occur'
        result['at_cut'] = cut[0]
        serial = r.machine.devices['serial']
        serial.input_bytes[8] = (15, 6)
        result['power_request_step'] = r.cpu.steps
        r.cpu.run(1_000_000)
        serial.input_bytes[8] = (15, 7)
        for _ in range((a.budget+4_999_999)//5_000_000):
            stop = r.cpu.run(5_000_000)
            if stop.reason != 'max_steps':
                result['stop'] = stop.to_dict()
                break
            if any(x['call'] == 'native-settings-store' for x in r.native_settings):
                break
        result['after'] = r.state('after')
        result['observation'] = 'COMPLETE'
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        signal.alarm(0)
        result.update(final_snapshot=r.save('final'), services=services, inputs=r.inputs,
            calls=r.calls, events=r.events, record_writes=record_writes,
            native_settings=r.native_settings, elapsed_seconds=time.monotonic()-started)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        r.machine.close()
        print(json.dumps(dict(name=a.name, observation=result.get('observation'),
            error=result.get('error'), stores=len(r.native_settings))), flush=True)


if __name__ == '__main__':
    main()
