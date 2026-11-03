"""Run disjoint offline replay processes; no device, network or agent use."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
import os
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def main():
    jobs = []
    for unit in ('50mm', '28mm', 'mount'):
        for error in (False, True):
            for kind in ('nested', 'loss'):
                label = f'{kind}-{unit}' + ('-error' if error else '')
                jobs.append((label, ['cutpoints', '--unit', unit, '--kind', kind] + (['--error'] if error else [])))
        jobs.append((f'h01-{unit}', ['h01_cuts', '--unit', unit]))
        jobs.append((f'variants-{unit}', ['variants', '--unit', unit]))
        if unit != '50mm':
            jobs.append((f'functional-{unit}', ['functional', '--unit', unit]))
    (OUT / 'local/tmp').mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(OUT / 'local/tmp'), PYTHONDONTWRITEBYTECODE='1')

    def execute(job):
        label, args = job
        argv = ['/usr/bin/python3', '-I', '-B', str(OUT / 'replay.py'), *args]
        started = time.time()
        with (OUT / 'local' / (label + '.log')).open('w') as stream:
            result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        return dict(label=label, argv=argv, returncode=result.returncode, seconds=round(time.time()-started, 3))

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending = [executor.submit(execute, job) for job in jobs]
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            (OUT / 'evidence/matrix.json').write_text(json.dumps(results, indent=2) + '\n')
            print(result['label'], result['returncode'], result['seconds'], flush=True)
    assert all(x['returncode'] == 0 for x in results), results


if __name__ == '__main__':
    main()
