"""Run one unit's complete reviewed matrix as recorded foreground commands."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, save

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('unit', choices=('50mm', '28mm', 'mount'))
    args = parser.parse_args()
    unit = args.unit
    (TREE / 'candidate/local/v34c-host/expand').chmod(0o755)
    commands = []
    for entry in ('fn2', 'ok', 'adj'):
        commands.append(('entry-' + entry, 'entry_switch.py', [unit, entry, '--at', '1']))
    for at in (1, 6, 7):
        commands.append(('early-' + str(at), 'failure_boundaries.py', [unit, str(at)]))
    for group in ('matrix', 'ah', 'exits', 'persistent'):
        commands.append((group, 'run_native.py', [group, unit]))
    commands += [('confirm', 'confirm_paths.py', [unit]), ('latch', 'latch_paths.py', [unit])]
    for at in (1, 6, 16, 17, 140):
        commands.append(('h08-' + str(at), 'concurrent_menu.py', ['other_menu', unit, '--at', str(at), '--reopen-fn2']))
    for group in ('recovery', 'fallback', 'nested'):
        commands.append((group, 'concurrent_menu.py', [group, unit]))
    for point in ('redraw', 'cache'):
        commands.append(('ui-' + point, 'ui_cutpoints.py', [point, unit]))
    for at in (1, 16):
        commands.append(('coalescing-' + str(at), 'coalescing.py', ['120', unit, '--at', str(at)]))
    rows = []
    for label, script, extra in commands:
        full_label = 'suite-' + unit + '-' + label
        command = ['/usr/bin/python3', '-I', '-B', str(OUT / 'run_recorded.py'), full_label,
                   '/usr/bin/python3', '-I', '-B', str(OUT / script), *extra]
        print('BEGIN', full_label, flush=True)
        code = subprocess.call(command, cwd=ROOT)
        rows.append(dict(label=label, script=script, arguments=extra, returncode=code))
        save('suite-' + unit + '.json', dict(status='RUNNING', unit=unit, commands=rows))
        print('END', full_label, 'exit', code, flush=True)
        if code:
            save('suite-' + unit + '.json', dict(status='FAIL', unit=unit, commands=rows))
            raise SystemExit(code)
    save('suite-' + unit + '.json', dict(status='PASS', unit=unit, commands=rows))
    print('PASS full native matrix', unit, len(rows), 'commands', flush=True)

if __name__ == '__main__':
    main()
