"""Finite, foreground-only reproducibility driver. No sleeps, polling or agents."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, LOCAL, guard, read
import argparse
import subprocess


def command(script, *args):
    subprocess.run(['python3', '-I', '-B', str(HERE / script), *map(str, args)],
                   cwd=ROOT, check=True, timeout=55)


def main():
    guard()
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['all', 'extract', 'models', 'targets', 'fits', 'analyze', 'verify', 'report'])
    a = p.parse_args()
    command('common.py')
    stages = ['extract', 'models', 'targets', 'fits', 'analyze', 'verify', 'report'] if a.stage == 'all' else [a.stage]
    for stage in stages:
        if stage == 'extract':
            for f in read(LOCAL / 'inventory.json'):
                command('extract.py', '--frame', f['id'])
                command('denoise.py', '--frame', f['id'])
        elif stage == 'models':
            for name in [f['id'] for f in read(LOCAL / 'inventory.json')] + ['gr3_standard_pooled', 'gr3_family_standard_pooled']:
                command('models.py', '--model', name)
            for mode in ('positive', 'negative'):
                command('targets.py', 'joint', '--mode', mode)
            command('models.py', '--compare')
        elif stage == 'targets':
            for group in ('gr3', 'gr4_hdf', 'gr4_b', 'gr4_0097'):
                for slot in ('01', '02'):
                    if group == 'gr4_0097' and slot == '01':
                        continue
                    command('targets.py', 'generate', '--group', group, '--slot', slot)
            request = ROOT / 'research/closed_loop/local/m20261021_r1_target_requests.json'
            measurement = ROOT / 'research/closed_loop/local/m20261021_r1.json'
            if request.exists() and measurement.exists():
                for group in ('gr3', 'gr4_hdf'):
                    command('adapters.py', '--group', group, '--requests', request, '--measurement', measurement,
                            '--out', LOCAL / 'targets' / f'closedloop_{group}.json', '--physical-model-iso', 200)
        elif stage == 'fits':
            for group in ('gr3', 'gr4_hdf'):
                for slot in ('01', '02'):
                    command('refit.py', '--group', group, '--slot', slot)
                    for kind, count in [('loo', 18), ('hue', 6), ('image', 1 if group == 'gr3' else 2)]:
                        for i in range(count):
                            command('refit.py', '--group', group, '--slot', slot, '--kind', kind, '--index', i)
        elif stage == 'analyze':
            command('analyze.py')
            command('noise.py')
        elif stage == 'verify':
            command('verify.py', '--stage', 'core')
            if (LOCAL / 'targets/closedloop_gr3.json').is_file():
                command('verify.py', '--stage', 'hooks')
            frames = [f['id'] for f in read(LOCAL / 'inventory.json')]
            for frame in frames:
                command('verify.py', '--stage', 'pairs', '--frame', frame)
            command('verify.py', '--stage', 'final')
        elif stage == 'report':
            command('report.py')
            command('verify.py', '--stage', 'final')
            command('seal.py')


if __name__ == '__main__':
    main()
