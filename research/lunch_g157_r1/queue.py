"""CPU-idle/memory admission for isolated single-thread numerical processes."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

assert sys.flags.isolated
assert os.getpriority(os.PRIO_PROCESS, 0) == 15
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
LOCAL.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / 'tools'))
import loadgate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=('inventory', 'analyze', 'targets', 'summary', 'diagnose', 'render', 'report', 'verify'))
    p.add_argument('--ids', nargs='*')
    p.add_argument('--max-workers', type=int, default=2)
    p.add_argument('--refresh', action='store_true', help='Archive existing output receipts before recomputing.')
    args = p.parse_args()
    lock = (LOCAL / 'queue.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.stage in ('inventory', 'summary', 'diagnose', 'render', 'report', 'verify'):
        result = dict(inventory='inventory.json', summary='summary.json', diagnose='diagnosis.json',
                      render='rendered-targets.json', report='report-receipt.json', verify='verification.json')[args.stage]
        script = dict(summary='summarize.py', render='render_targets.py', report='write_report.py').get(args.stage, args.stage + '.py')
        jobs = [(args.stage, [str(HERE / script)], LOCAL / result)]
    else:
        rows = json.loads((LOCAL / 'inventory.json').read_text())
        ids = args.ids or [r['id'] for r in rows if r['group'] != 'previous_day']
        script = 'analyze.py' if args.stage == 'analyze' else 'targets.py'
        result = 'result.json' if args.stage == 'analyze' else 'targets.json'
        jobs = [(pid, [str(HERE / script), pid], LOCAL / 'frames' / pid / result) for pid in ids]
    if args.refresh:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        for key, argv, done in jobs:
            if done.exists():
                history = done.parent / 'history'
                history.mkdir(exist_ok=True)
                (history / (done.stem + '-' + stamp + done.suffix)).write_bytes(done.read_bytes())
                done.unlink()
    jobs = [j for j in jobs if not j[2].exists()]
    running = {}
    failed = []
    last = 0
    started = time.time()
    receipts = []
    tag = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = LOCAL / 'queues' / (args.stage + '-' + tag)
    out.mkdir(parents=True, exist_ok=False)
    while jobs or running:
        for key, data in list(running.items()):
            proc, log, job, began = data
            code = proc.poll()
            if code is None:
                continue
            log.close()
            del running[key]
            receipts.append(dict(id=key, exit_code=code, seconds=time.time()-began, pid=proc.pid))
            print('FINISH', key, 'exit', code, 'seconds', round(time.time()-began, 1), flush=True)
            if code == 75:
                jobs.append(job)
            elif code != 0 or not job[2].is_file():
                failed.append(key)
        if failed and not running:
            break
        if jobs and not failed:
            cap, info = loadgate.cap(len(running), per_queue_max=args.max_workers)
            with (out / 'admission.jsonl').open('a') as f:
                f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), **info)) + '\n')
            if cap > len(running):
                job = jobs.pop(0)
                key, argv, done = job
                log = (out / (key + '-' + str(len(receipts)) + '.log')).open('w')
                command = [sys.executable, '-I', '-B', *argv]
                label = 'targets-' + key if args.stage == 'targets' else key
                proof = out / (key + '-' + str(len(receipts)) + '-admission.json')
                proof.write_text(json.dumps(dict(parent_pid=os.getpid(), label=label,
                                 running_before=len(running), **info)) + '\n')
                env = dict(os.environ, LUNCH_QUEUE_ADMISSION=str(proof))
                proc = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
                running[key] = proc, log, job, time.time()
                print('START', key, 'pid', proc.pid, 'idle cores', info['idle_cores'], flush=True)
        if time.time() - last >= 40:
            print('QUEUE', args.stage, 'pending', len(jobs), 'running', list(running), 'failed', failed, flush=True)
            last = time.time()
        (out / 'receipt.json').write_text(json.dumps(dict(rows=receipts, failed=failed,
            pending=[j[0] for j in jobs], running=list(running), elapsed_seconds=time.time()-started), indent=2) + '\n')
        if jobs or running:
            time.sleep(3 if running else 10)
    if failed:
        raise SystemExit('Numerical failure, preserved without automatic retry: ' + ', '.join(failed))
    print('QUEUE COMPLETE', args.stage, len(receipts), flush=True)


if __name__ == '__main__':
    main()
