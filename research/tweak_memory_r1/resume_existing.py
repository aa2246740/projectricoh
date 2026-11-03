"""Re-run interrupted cold phases from a completed retained UI snapshot."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from repro_flow import phase


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-prefix', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--unit', choices=('mount', '28mm', '50mm'), required=True)
    p.add_argument('--kind', choices=('builtin', 'look', 'user'), required=True)
    p.add_argument('--number', type=int, required=True)
    a = p.parse_args()
    old, name = a.source_prefix, a.name
    receipt = HERE/'evidence'/(name+'-flow.json')
    assert not receipt.exists()
    settings = HERE/'local'/(old+'-exit1-final-S-persistent.bin')
    target = HERE/'local'/(old+'-manual-accept-target.bin')
    assert settings.exists() and target.exists()
    engine = ROOT/'firmware/engine_v67_g155c'
    common = ['--engine', engine, '--elf', engine/'candidate/local/boot-on/engine.elf']
    rows = []
    result = dict(status='RUNNING', source_prefix=old, unit=a.unit, kind=a.kind,
                  phases=rows, started=datetime.datetime.now(datetime.timezone.utc).isoformat())
    def run(script, args, suffix, backend='c'):
        phase(script, args, name+'-'+suffix+'-run', rows, backend)
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    try:
        run('cold_run.py', ['--name', name+'-cold', '--unit', a.unit,
            '--dat', ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT',
            '--settings-source', settings, '--budget', 650000000, '--timeout', 10800], 'cold')
        cold = HERE/'local'/(name+'-cold-session.pkl.z')
        run('accept.py', ['--source', cold, *common, '--name', name+'-cold-accept',
            '--expected', target], 'cold-accept')
        run('probe.py', ['--mode', 'inspect', '--name', name+'-menu', '--source', cold,
            *common, '--kind', a.kind, '--number', a.number], 'menu')
        menu = json.loads((HERE/'evidence'/(name+'-menu.json')).read_text())
        assert menu['open_menu_W_T'] == menu['open_controls_W_T'] == 0
        assert menu['first_menu']['levels'] == menu['first_controls']['levels'] == menu['final']['engine_levels']
        run('accept.py', ['--source', HERE/'local'/(name+'-menu-final.pkl.z'), *common,
            '--name', name+'-menu-accept', '--expected', target], 'menu-accept')
        for backend in ('c', 'python'):
            run('glyphs.py', ['--source', HERE/'local'/(name+'-menu-first-menu.pkl.z'),
                *common, '--name', name+'-menu-glyphs'], 'glyphs-'+backend, backend)
        result['status'] = 'PASS'
    except BaseException as exc:
        result.update(status='OPEN', error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
        raise
    finally:
        result['ended'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
