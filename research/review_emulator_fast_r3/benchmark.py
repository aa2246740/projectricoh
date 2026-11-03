"""Alternating fresh-process pairs; never run with another R3 worker active."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import review as V


def sample_load():
    return dict(load=os.getloadavg(), processes=subprocess.run(
        ['/bin/ps', '-axo', 'pid,ppid,ni,%cpu,etime,comm', '-r'], capture_output=True, text=True).stdout.splitlines()[:18])


def child(backend, name, steps):
    sys.addaudithook(V.fence)
    os.environ['TMPDIR'] = str(V.TEMP)
    R = V.runner(); os.environ['GXR_STRICT_REFERENCE_ORACLE'] = 'legacy'
    R.setup(backend)
    ctx = R.construct('main', name); c = ctx.machine.cpu
    before = sample_load(); wall = time.perf_counter(); cpu = time.process_time()
    stop = c.run(steps)
    cpu = time.process_time() - cpu; wall = time.perf_counter() - wall
    after = sample_load()
    state = V.fingerprint(ctx)
    stats = c._native_driver.stats() if c._native_driver else None
    row = dict(backend=backend, steps=c.steps, stop=stop.to_dict(), seconds=wall, cpu_seconds=cpu,
               before=before, after=after, state=state, stats=stats, library=str(c.library_path),
               library_sha256=V.sha_file(c.library_path), nice=os.getpriority(os.PRIO_PROCESS, 0))
    assert c.steps == steps and stop.reason == 'max_steps'
    if backend == 'native':
        assert stats['instructions'] == steps and not stats['python_bus_calls'] and not stats['hle_callbacks']
    c.close()
    (V.RUNS / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(name=name, seconds=wall, cpu_seconds=cpu, steps=steps)), flush=True)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    p = argparse.ArgumentParser(); p.add_argument('--child', choices=('native', 'reference'))
    p.add_argument('--name'); p.add_argument('--pairs', type=int, default=5)
    p.add_argument('--label', default='', help='Fresh namespace suffix for a repeat measurement')
    p.add_argument('--steps', type=int, default=50000000); p.add_argument('--kind', choices=('main', 'input'), default='main')
    a = p.parse_args()
    if a.child:
        return child(a.child, a.name, a.steps)
    if a.label and not a.label.replace('-', '').replace('_', '').isalnum():
        raise ValueError('use a simple fresh benchmark label')
    suffix = '-' + a.label if a.label else ''
    target = V.RUNS / ('benchmark-' + a.kind + suffix + '.json'); assert not target.exists()
    result = dict(kind=a.kind, pairs=[], started=time.strftime('%FT%TZ', time.gmtime()))
    for pair in range(a.pairs):
        rows = {}
        for backend in ('reference', 'native'):
            name = 'bench-' + a.kind + suffix + '-' + str(pair + 1) + '-' + backend
            if a.kind == 'main':
                cmd = [sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                       '--child', backend, '--name', name, '--steps', str(a.steps)]
            else:
                cmd = [sys.executable, '-I', '-B', str(HERE / 'review.py'), 'recipe', 'input_case',
                       '--backend', backend, '--name', name, '--steps', str(a.steps)]
            with (V.RUNS / (name + '-controller.log')).open('x') as log:
                run = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1700)
            if run.returncode:
                result['error'] = dict(command=cmd, returncode=run.returncode)
                target.write_text(json.dumps(result, indent=2) + '\n')
                raise RuntimeError(result['error'])
            rows[backend] = json.loads((V.RUNS / (name + '.json')).read_text())
        if a.kind == 'main':
            assert rows['reference']['state'] == rows['native']['state']
            left, right = (rows[b]['seconds'] for b in ('reference', 'native'))
        else:
            assert rows['reference']['full_state'] == rows['native']['full_state']
            assert rows['reference']['receipt'] == rows['native']['receipt']
            left, right = (rows[b]['product_seconds'] for b in ('reference', 'native'))
        entry = dict(pair=pair + 1, reference=rows['reference'], native=rows['native'], ratio=left / right)
        result['pairs'].append(entry)
        target.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(dict(kind=a.kind, pair=pair + 1, reference_seconds=left, native_seconds=right, ratio=left / right)), flush=True)
    result['median_pair_ratio'] = statistics.median(r['ratio'] for r in result['pairs'])
    result['ratio_range'] = [min(r['ratio'] for r in result['pairs']), max(r['ratio'] for r in result['pairs'])]
    result['status'] = 'PASS'
    target.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
