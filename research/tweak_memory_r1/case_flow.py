"""Run a unit/category from a real cold origin through retained record cycles."""
import argparse
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
    p.add_argument('--case', choices=('mount-builtin', 'mount-look', 'mount-user', '28mm-builtin', '50mm-builtin', '50mm-user'), required=True)
    p.add_argument('--resume-init', type=Path)
    p.add_argument('--cycles', type=int, choices=(1, 2), default=2)
    p.add_argument('--adjust-one', action='store_true')
    p.add_argument('--capture-boot', action='store_true')
    p.add_argument('--prefix')
    p.add_argument('--profile',choices=('test',),default='test')
    a = p.parse_args()
    unit, kind = a.case.split('-')
    number = 3 if kind == 'builtin' else 1 if kind == 'look' else 2
    prefix = a.prefix or 'g155c-'+a.case
    engine = ROOT/'firmware/engine_v67_g155c'
    elf = engine/('candidate/local/boot-on/engine.elf' if a.profile=='test' else 'candidate/local/release-auto/engine.elf')
    dat = ROOT/('firmware/package_v310_g155c_test/GXRCE.DAT' if a.profile=='test' else 'firmware/package_v310_g155c/GXRCE.DAT')
    image = ROOT/'firmware/image_v310/local/ilaunch3'
    common = ['--engine', engine, '--elf', elf]
    rows = []
    state = dict(case=a.case, profile=a.profile, status='RUNNING', phases=rows, cycles=a.cycles,
        resume_init=str(a.resume_init) if a.resume_init else None)
    receipt = HERE/'evidence'/(prefix+'-flow.json')
    assert not receipt.exists()
    def run(script, args, suffix, backend='c'):
        phase(script, args, prefix+'-'+suffix+'-run', rows, backend)
        receipt.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    def probe(mode, name, source):
        run('probe.py', ['--mode', mode, '--name', name, '--source', source, *common,
            '--kind', kind, '--number', number], name[len(prefix)+1:])
        result = json.loads((HERE/'evidence'/(name+'.json')).read_text())
        return HERE/'local'/(name+'-final.pkl.z'), ROOT/result['settings']['persistent_path']
    def cold(name, settings=None):
        args = ['--name', name, '--unit', unit, '--dat', dat, '--image', image,
            '--budget', '650000000', '--timeout', '14400']
        if settings:
            args += ['--settings-source', settings]
        if a.capture_boot:
            args += ['--capture-boot']
        run('cold_run.py', args, name[len(prefix)+1:])
        return HERE/'local'/(name+'-session.pkl.z')
    def accept(source, suffix, expected=None):
        args = ['--source', source, *common, '--name', prefix+'-'+suffix]
        if expected:
            args += ['--expected', expected]
        run('accept.py', args, suffix)
        return HERE/'local'/(prefix+'-'+suffix+'-target.bin')
    try:
        source = a.resume_init or cold(prefix+'-init')
        source, _ = probe('choose', prefix+'-choose', source)
        source, _ = probe('tweak-only' if a.adjust_one else 'controls', prefix+'-controls', source)
        target = accept(source, 'manual-accept')
        manual = json.loads((HERE/'evidence'/(prefix+'-manual-accept.json')).read_text())
        controls = json.loads((HERE/'evidence'/(prefix+'-controls.json')).read_text())
        assert controls['start']['engine_levels'] != controls['final']['engine_levels'], 'control input did not change the active values'
        assert any(value != (100 if index == 0 else 0) for index, value in enumerate(manual['levels'])), 'nonzero controls are required'
        code = bytes.fromhex(manual['record'])[5]
        assert (1 <= code <= 8 if kind == 'builtin' else
                code == 0x40+number-1 if kind == 'look' else code == 0x80+number-1), (
            'manual category differs from requested category', kind, number, code)
        state['manual_identity'] = dict(requested_category=kind, requested_number=number,
            record_category_code=code, actual_slot=manual['slot'], actual_effect=manual['effect'])
        source, settings = probe('exit', prefix+'-exit1', source)
        for cycle in range(1, a.cycles+1):
            source = cold(prefix+'-cold'+str(cycle), settings)
            accept(source, 'cold'+str(cycle)+'-accept', target)
            source, _ = probe('inspect', prefix+'-menu'+str(cycle), source)
            menu = json.loads((HERE/'evidence'/(prefix+'-menu'+str(cycle)+'.json')).read_text())
            assert menu['open_menu_W_T'] == menu['open_controls_W_T'] == 0
            assert menu['first_menu']['levels'] == menu['first_controls']['levels'] == menu['final']['engine_levels']
            accept(source, 'menu'+str(cycle)+'-accept', target)
            first = HERE/'local'/(prefix+'-menu'+str(cycle)+'-first-menu.pkl.z')
            for backend in (('c', 'python') if cycle == 1 else ('c',)):
                run('glyphs.py', ['--source', first, *common, '--name', prefix+'-menu'+str(cycle)+'-glyphs'],
                    'menu'+str(cycle)+'-glyphs-'+backend, backend)
            if cycle == 1 and a.cycles == 2:
                source, _ = probe('tweak-only', prefix+'-tweak-only', source)
                changed = json.loads((HERE/'evidence'/(prefix+'-tweak-only.json')).read_text())
                before, after = changed['first_menu'], changed['final']
                assert bytes.fromhex(before['record'])[5:8] == bytes.fromhex(after['record'])[5:8]
                assert before['engine_levels'] != after['engine_levels']
                target = accept(source, 'tweak-only-accept')
                source, settings = probe('exit', prefix+'-exit2', source)
        state['status'] = 'PASS'
    except BaseException as exc:
        state.update(status='OPEN', error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
        raise
    finally:
        receipt.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
