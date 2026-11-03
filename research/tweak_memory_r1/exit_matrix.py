"""Compare exit paths from one real completed nonzero control state."""
import argparse
import json
from pathlib import Path
import signal
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime import Runtime, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    a = p.parse_args()
    rows = []
    for key in ('OK', 'ADJ', 'HALF', 'MENU', 'timeout'):
        name = a.name+'-'+key.lower()
        output = HERE/'evidence'/(name+'.json')
        assert not output.exists()
        r = Runtime(a.source, name, a.engine, a.elf)
        result = dict(status='OPEN', exit_key=key, source=str(a.source),
            source_sha256=sha(a.source.read_bytes()), native_state_presets=[], layer='模拟器实测')
        signal.alarm(7200)
        try:
            result['before'] = r.state('before-exit')
            result['before_tick'] = r.u(0x200d183c)
            if key == 'timeout':
                r.run(120_000_000)
            else:
                r.key(key)
            result['after_tick'] = r.u(0x200d183c)
            result['after'] = r.state('after-exit')
            result['settings'] = r.settings('exit')
            assert result['after']['record'] == result['before']['record']
            assert result['after']['engine_levels'] == result['before']['engine_levels']
            result['status'] = 'PASS'
            result['menu_closed'] = result['after']['activity'] != 8 or result['after']['state'] != 56
            if key == 'timeout':
                result['automatic_exit_observed'] = result['menu_closed']
        except Exception as exc:
            result['error'] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        finally:
            signal.alarm(0)
            result['snapshot'] = r.save('final')
            result.update(calls=r.calls, events=r.events, inputs=r.inputs, native_settings=r.native_settings)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
            r.machine.close()
        rows.append(dict(name=name, status=result['status'], error=result.get('error')))
        print(json.dumps(rows[-1]), flush=True)
    (HERE/'evidence'/(a.name+'-matrix.json')).write_text(json.dumps(rows, indent=2)+'\n')
    if any(row['status'] != 'PASS' for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
