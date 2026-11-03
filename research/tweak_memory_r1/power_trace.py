"""Observe original setting stores after a declared external power button input."""
import argparse
import json
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import Runtime, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--while-menu', action='store_true')
    p.add_argument('--open-value', action='store_true')
    p.add_argument('--budget', type=int, default=180_000_000)
    a = p.parse_args()
    path = HERE/'evidence'/(a.name+'.json')
    assert not path.exists()
    r = Runtime(a.source, a.name, a.engine, a.elf)
    result = dict(status='OPEN', source_sha256=sha(a.source.read_bytes()), native_state_presets=[],
        layer='模拟器实测', input_boundary='serial input byte 8, power level 6 then 7')
    record_writes = []
    S = r.u(0x200c0dac)
    r.cpu.add_write_trace(S+0xfd4, S+0xffc, lambda at, data:record_writes.append(dict(
        step=r.cpu.steps, pc=hex(r.cpu.get_reg('pc')), address=hex(at), data=bytes(data).hex())))
    signal.alarm(7200)
    try:
        result['start'] = r.state('start')
        if a.open_value:
            assert a.while_menu and result['start']['screen'] == 2
            r.key('DISP')
            assert r.state('value')['screen'] == 3
            r.key('UP')
            result['value_before_power'] = r.state('value-before-power')
            assert result['value_before_power']['levels'] == result['value_before_power']['engine_levels']
            assert bytes.fromhex(result['value_before_power']['record'])[8:28] == r.cpu.read(r.at('g.tweak'), 20)
            result['completed_source'] = r.save('value-before-power')
        if not a.while_menu:
            for _ in range(20):
                if r.u(0x205d9c00) == 5:
                    break
                r.run(5_000_000)
        result['viewfinder'] = r.state('viewfinder')
        assert result['viewfinder']['state'] == (56 if a.while_menu else 5)
        result['ready_snapshot']=r.save('before-power-input')
        serial = r.machine.devices['serial']
        serial.input_bytes[8] = (15, 6)
        r.run(1_000_000)
        serial.input_bytes[8] = (15, 7)
        for _ in range((a.budget+4_999_999)//5_000_000):
            r.run(5_000_000)
            if r.native_settings and any(x['call'] == 'native-settings-store' for x in r.native_settings):
                break
        result['final'] = r.state('after-power-input')
        stores = [x for x in r.native_settings if x['call'] == 'native-settings-store']
        result['native_store_observed'] = bool(stores)
        expected = result.get('value_before_power', result['start'])['record']
        result['record_equal_at_all_stores'] = bool(stores) and all(x['record'] == expected for x in stores)
        result['store_entry_check'] = 'PASS' if result['record_equal_at_all_stores'] else 'OPEN'
        result['status'] = 'OPEN'
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
    finally:
        signal.alarm(0)
        result.update(snapshot=r.save('final'), native_settings=r.native_settings, events=r.events, record_writes=record_writes,
            boundary='Original store entry and bytes only; a completed physical power cycle and NAND retention are separate')
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        r.machine.close()
        print(json.dumps(dict(name=a.name, status=result['status'], stores=result.get('native_store_observed'), error=result.get('error'))))


if __name__ == '__main__':
    main()
