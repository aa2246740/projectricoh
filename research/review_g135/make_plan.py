"""Expand the 81 regression groups (names/args from the g129 plan), the three extra suites, and bind them to the g135 runner."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent

def main():
    old = json.loads((ROOT / 'research/review_g129/plan.json').read_text())
    jobs, rows = [], []
    for job in old['jobs']:
        if not job['name'].startswith('group'):
            continue
        args = job['args']
        assert args[:5] == ['research/review_g129/retained.py', '--job', job['name'], '--crc-mode', 'host']
        script_args = args[5:]
        jobs.append({'name': job['name'], 'kind': 'regression', 'args': ['research/review_g135/runner.py', '--crc-implementation', 'host', *script_args]})
    matrix = [row for row in old['matrix']]
    assert len(jobs) == 81 == len(matrix)
    assert [j['name'] for j in jobs] == [r['name'] for r in matrix]
    (WORK / 'plan.json').write_text(json.dumps({'workers': 3, 'timeout_seconds': 4200, 'jobs': jobs, 'matrix': matrix}, indent=1) + '\n')
    print(len(jobs))

if __name__ == '__main__':
    main()
