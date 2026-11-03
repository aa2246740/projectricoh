"""Run exit checks and a fresh MAIN replay from a completed manual record."""
import argparse
import contextlib
import datetime
import json
import os
from pathlib import Path
import runpy
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def phase(script, args, name, rows, backend='c'):
    path = HERE/'evidence'/(name+'.log')
    assert not path.exists(), path
    old_argv, old_backend = sys.argv, os.environ.get('GXR_HARNESS_BACKEND')
    old_path = sys.path[:]
    old_modules = sys.modules.copy() if script == 'build.py' else None
    sys.argv = [str(HERE/script), *map(str, args)]
    os.environ['GXR_HARNESS_BACKEND'] = backend
    started = time.monotonic()
    row = dict(name=name, script=script, args=list(map(str, args)), backend=backend,
        started=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        with path.open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            try:
                runpy.run_path(str(HERE/script), run_name='__main__')
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
        row['status'] = 'PASS'
    except BaseException as exc:
        row.update(status='OPEN', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        sys.argv = old_argv
        sys.path[:] = old_path
        if old_modules is not None:
            for key in set(sys.modules)-set(old_modules):
                sys.modules.pop(key, None)
            sys.modules.update(old_modules)
        if old_backend is None:
            os.environ.pop('GXR_HARNESS_BACKEND', None)
        else:
            os.environ['GXR_HARNESS_BACKEND'] = old_backend
        row['elapsed_seconds'] = time.monotonic()-started
        rows.append(row)
        print(json.dumps(row), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', choices=('g154', 'g155b'), required=True)
    p.add_argument('--restart-only', action='store_true')
    a = p.parse_args()
    old = a.version == 'g154'
    engine = ROOT/('firmware/engine_v63_g154' if old else 'firmware/engine_v66_g155b')
    elf = engine/('candidate/local/full-r13/engine.elf' if old else 'candidate/local/boot-on/engine.elf')
    dat = ROOT/('firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT' if old else 'firmware/package_v310_g155b_test/GXRCE.DAT')
    image = ROOT/('firmware/package_v39_g154_test/local/SD_ROOT/ilaunch3' if old else 'firmware/image_v310/local/ilaunch3')
    prefix = 'repro-'+a.version
    source = HERE/'local'/('resume-'+a.version+'-hcb-final.pkl.z')
    common = ['--engine', engine, '--elf', elf]
    rows = []
    receipt = HERE/'evidence'/(prefix+('-restart-flow.json' if a.restart_only else '-flow.json'))
    assert not receipt.exists()
    try:
        if not a.restart_only:
            phase('accept.py', ['--source', source, *common, '--name', prefix+'-manual-accept'], prefix+'-manual-check', rows)
            phase('exit_matrix.py', ['--source', source, *common, '--name', prefix+'-exits'], prefix+'-exits-run', rows)
        settings = HERE/'local'/(prefix+'-exits-ok-exit-S-persistent.bin')
        phase('cold_run.py', ['--name', prefix+'-restart', '--unit', 'mount', '--dat', dat,
            '--image', image, '--settings-source', settings, '--budget', '650000000', '--timeout', '14400'],
            prefix+'-restart-run', rows)
        cold = HERE/'local'/(prefix+'-restart-session.pkl.z')
        if not old:
            phase('accept.py', ['--source', cold, *common, '--name', prefix+'-cold-accept',
                '--expected', HERE/'local'/(prefix+'-manual-accept-target.bin')], prefix+'-cold-check', rows)
        phase('probe.py', ['--mode', 'inspect', '--name', prefix+'-first-menu', '--source', cold, *common], prefix+'-menu-run', rows)
        final = HERE/'local'/(prefix+'-first-menu-final.pkl.z')
        phase('accept.py', ['--source', final, *common, '--name', prefix+'-panel-accept',
            '--expected', HERE/'local'/(prefix+'-manual-accept-target.bin')], prefix+'-panel-check', rows)
        for backend in ('c', 'python'):
            phase('glyphs.py', ['--source', final, *common, '--name', prefix+'-panel-glyphs'],
                prefix+'-glyphs-'+backend+'-run', rows, backend)
    finally:
        receipt.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    main()
