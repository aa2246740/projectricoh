from pathlib import Path
import asyncio
import datetime
import hashlib
import json
import os
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
QUEUE = OUT / 'queue.json'
EVENTS = OUT / 'evidence/runs.jsonl'
STATE = OUT / 'evidence/scheduler.json'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record(value):
    with EVENTS.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
    print(json.dumps(value, ensure_ascii=False), flush=True)


async def run(job, deadline):
    folder = OUT / 'local/jobs' / job['name']
    (folder / 'local/tmp').mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REVIEW_JOB=job['name'], TMPDIR=str(folder / 'local/tmp'))
    script = ROOT / 'research/review_g135_gpt' / job.get('driver', 'bridge.py')
    command = ['/usr/bin/python3', '-I', '-B', str(script)] + job['args']
    started = datetime.datetime.now(datetime.timezone.utc)
    with (folder / 'console.log').open('wb') as stream:
        process = await asyncio.create_subprocess_exec(*command, cwd=str(ROOT), env=env, stdout=stream, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        record({'event': 'start', 'name': job['name'], 'pid': process.pid, 'utc': utc(), 'timeout_seconds': job.get('timeout_seconds', 4200)})
        remaining = (deadline - started).total_seconds()
        limit = min(job.get('timeout_seconds', 4200), remaining)
        status = 'FINISHED'
        try:
            code = await asyncio.wait_for(process.wait(), timeout=max(0, limit))
        except asyncio.TimeoutError:
            status = 'TIMEBOX' if remaining < job.get('timeout_seconds', 4200) else 'TIMEOUT'
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                code = await process.wait()
    result = {'event': 'finish', 'name': job['name'], 'returncode': code, 'execution': status, 'seconds': round((datetime.datetime.now(datetime.timezone.utc) - started).total_seconds(), 3), 'utc': utc(), 'driver_sha256': hashlib.sha256(script.read_bytes()).hexdigest()}
    (folder / 'execution.json').write_text(json.dumps(result, indent=2) + '\n')
    record(result)
    return result


async def main():
    configuration = json.loads(QUEUE.read_text())
    deadline = datetime.datetime.fromisoformat(configuration['deadline_utc'].replace('Z', '+00:00'))
    done = set()
    active = {}
    results = []
    peak = 0
    record({'event': 'scheduler-start', 'pid': os.getpid(), 'utc': utc(), 'workers': configuration['workers'], 'wait_mode': 'process-completion'})
    while True:
        configuration = json.loads(QUEUE.read_text())
        pending = [job for job in configuration['jobs'] if job['name'] not in done and job['name'] not in active.values()]
        while pending and len(active) < configuration['workers'] and datetime.datetime.now(datetime.timezone.utc) < deadline:
            job = pending.pop(0)
            task = asyncio.create_task(run(job, deadline))
            active[task] = job['name']
            peak = max(peak, len(active))
        STATE.write_text(json.dumps({'pid': os.getpid(), 'utc': utc(), 'active': list(active.values()), 'done': sorted(done), 'peak_workers': peak, 'pending': [job['name'] for job in pending]}, indent=2) + '\n')
        if not active:
            if datetime.datetime.now(datetime.timezone.utc) >= deadline:
                break
            record({'event': 'scheduler-idle', 'utc': utc()})
            try:
                command = await asyncio.wait_for(asyncio.to_thread(sys.stdin.readline), timeout=(deadline - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
            except asyncio.TimeoutError:
                break
            if command.strip() == 'stop' or command == '':
                break
            continue
        finished, unused = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
        for task in finished:
            done.add(active.pop(task))
            results.append(task.result())
    record({'event': 'scheduler-finish', 'utc': utc(), 'peak_workers': peak, 'finished': len(results)})


asyncio.run(main())
