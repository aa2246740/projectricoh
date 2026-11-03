"""One serial review queue. It may coexist with one other firmware process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def jobs():
    rows = [('replay-old04', ['replay_all.py', '--name', 'old04'], 1000)]
    for case in ('label-long', 'label-nul', 'stop-watch-order', 'watch-stop-order'):
        for backend in ('native', 'reference'):
            rows.append(('control-' + case + '-' + backend,
                         ['control_probes.py', '--case', case, '--backend', backend], 180))
    rows.append(('key-off-reference', ['snapshot_probes.py', 'recipe-off', '--name', 'key-off-reference', '--backend', 'reference'], 240))
    rows.append(('hold-reference', ['snapshot_probes.py', 'hold', '--name', 'hold-reference', '--backend', 'reference'], 500))
    rows.append(('release-reference', ['review.py', 'recipe', 'flows', '--backend', 'reference', '--oracle', 'legacy',
                                      '--kind', 'release', '--name', 'release-reference', '--timeout', '1700'], 1730))
    for backend in ('native', 'reference'):
        rows.append(('recovery-' + backend, ['review.py', 'recipe', 'flows', '--backend', backend, '--oracle', 'legacy',
                                            '--kind', 'recovery', '--name', 'recovery-' + backend, '--timeout', '900'], 930))
    for backend in ('native', 'reference'):
        rows.append(('sd-keys-' + backend, ['review.py', 'recipe', 'sd_sequence', '--backend', backend, '--name', 'sd-keys-' + backend], 700))
    for backend in ('native', 'reference'):
        rows.append(('input-segments-' + backend, ['review.py', 'recipe', 'input_case', '--backend', backend,
                                                  '--name', 'input-segments-' + backend, '--steps', '1000054',
                                                  '--segment', 'IDLE:1000000', '--segment', 'HALF=down:23',
                                                  '--segment', 'HALF=up:31'], 400))
    for backend in ('native', 'reference'):
        rows.append(('input-resume-' + backend, ['review.py', 'recipe', 'input_resume', '--backend', backend], 400))
    rows.append(('smc-reference', ['review.py', 'recipe', 'edge_cases', '--backend', 'reference', '--case', 'self-modifying', '--name', 'smc-reference'], 180))
    rows.append(('snapshot-acceptance', ['review.py', 'recipe', 'snapshot_acceptance'], 600))
    rows.append(('model-matrix', ['matrices.py'], 1700))
    return rows


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    target = HERE / 'runs/functional-queue.json'; assert not target.exists()
    result = dict(started=time.strftime('%FT%TZ', time.gmtime()), rows=[])
    for name, args, timeout in jobs():
        print(json.dumps(dict(start=name, utc=time.strftime('%FT%TZ', time.gmtime()))), flush=True)
        start = time.perf_counter()
        with (HERE / 'runs' / (name + '-queue.log')).open('x') as log:
            try:
                run = subprocess.run([sys.executable, '-I', '-B', str(HERE / args[0]), *args[1:]],
                                     cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
                                     env=dict(os.environ, GXR_STRICT_REFERENCE_ORACLE='legacy'))
                code = run.returncode
            except subprocess.TimeoutExpired:
                code = 'TIMEOUT'
        row = dict(name=name, command=args, returncode=code, seconds=time.perf_counter() - start)
        result['rows'].append(row); target.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(row), flush=True)
    result['status'] = 'COMPLETE'
    target.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
