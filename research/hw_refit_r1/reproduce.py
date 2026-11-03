"""Foreground reproduction using the existing frozen corpus, no firmware build."""
import argparse
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fit-missing', action='store_true')
    args = parser.parse_args()
    commands = [('run.py', 'prepare'), ('verify.py', 'core')]
    if args.fit_missing:
        commands.append(('run.py', 'fit', '--nfev', '80'))
        for scale in ('2', '4'):
            commands.append(('run.py', 'fit', '--routes', 'all_Y_add,all_Y_Y,all_C_add,all_C_Y',
                             '--reg-scale', scale, '--nfev', '80'))
        commands.extend([('unfrozen06.py',), ('radius_sensitivity.py',)])
    commands.extend([('fix_gray.py',), ('integer_refine.py',), ('verify.py', 'all'), ('unit_sensitivity.py',), ('best_cases.py',), ('report.py',), ('seal.py',)])
    for script, *rest in commands:
        argv = [sys.executable, '-I', '-B', str(HERE / script), *rest]
        print('running', script, *rest, flush=True)
        subprocess.run(argv, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
