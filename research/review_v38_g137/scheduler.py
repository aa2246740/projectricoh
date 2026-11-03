import asyncio
import datetime as dt
import json
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v38_g137'
START = (dt.datetime.fromisoformat(os.environ['REVIEW_START']) if os.environ.get('REVIEW_START')
         else dt.datetime(2026, 10, 30, 5, 26, 28, tzinfo=dt.timezone.utc))
DEADLINE = START + dt.timedelta(hours=3.5)
JOBS = json.loads((OUT / os.environ.get('REVIEW_QUEUE', 'queue.json')).read_text())
EVENTS = OUT / 'evidence/runs.jsonl'
pending = list(JOBS)
active = {}
results = {}
changed = None
closed = False
maximum = 0

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def record(row):
    row['utc'] = stamp()
    with EVENTS.open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps(row, ensure_ascii=False), flush=True)

async def run(job):
    global maximum
    started = time.monotonic()
    command = ['sandbox-exec', '-f', str(OUT / 'offline.sb'), '/usr/bin/python3', '-I', '-B',
               str(OUT / 'legacy_call.py'), job['name'], *job['args']]
    env = dict(os.environ)
    env.update(job.get('env', {}))
    process = await asyncio.create_subprocess_exec(*command, cwd=str(ROOT), env=env,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                    start_new_session=True, limit=4 * 1024 * 1024)
    maximum = max(maximum, len(active))
    record({'event': 'start', 'name': job['name'], 'pid': process.pid,
            'timeout_seconds': job['timeout_seconds'], 'active': len(active)})
    log = OUT / 'local' / (job['name'] + '.log')
    async def collect():
        with log.open('w') as stream:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode('utf-8', 'replace')
                if text.startswith('    ') and not text.lstrip().startswith('File '):
                    continue
                stream.write(text)
                stream.flush()
        return await process.wait()
    available = (DEADLINE - dt.datetime.now(dt.timezone.utc)).total_seconds()
    status = 'DONE'
    try:
        code = await asyncio.wait_for(collect(), timeout=min(job['timeout_seconds'], max(0.01, available)))
    except asyncio.TimeoutError:
        status = 'TIMEBOX' if available < job['timeout_seconds'] else 'TIMEOUT'
        os.killpg(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=8)
        except asyncio.TimeoutError:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
        code = process.returncode
    result = {'name': job['name'], 'returncode': code, 'status': status,
              'seconds': round(time.monotonic() - started, 2),
              'dat_sha256': '78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'}
    (OUT / 'evidence' / (job['name'] + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    results[job['name']] = result
    active.pop(job['name'])
    record(dict(result, event='finish'))
    changed.set()

async def main():
    global closed, changed
    changed = asyncio.Event()
    record({'event': 'scheduler', 'pid': os.getpid(), 'slots': 3,
            'deadline_utc': DEADLINE.isoformat(), 'jobs': len(pending)})
    loop = asyncio.get_running_loop()
    def incoming():
        global closed
        line = sys.stdin.readline()
        if not line:
            closed = True
            loop.remove_reader(sys.stdin.fileno())
        else:
            command = json.loads(line)
            if command.get('close'):
                closed = True
                loop.remove_reader(sys.stdin.fileno())
            else:
                additions = command.get('jobs', [])
                pending.extend(additions)
                record({'event': 'added', 'names': [j['name'] for j in additions]})
        changed.set()
    loop.add_reader(sys.stdin.fileno(), incoming)
    changed.set()
    while pending or active or not closed:
        await changed.wait()
        changed.clear()
        now = dt.datetime.now(dt.timezone.utc)
        if now >= DEADLINE:
            for job in pending:
                record({'event': 'not_started', 'name': job['name'], 'status': 'TIMEBOX'})
            pending.clear()
            closed = True
        while len(active) < 3:
            ready = next((j for j in pending if all(
                dep in results and results[dep]['returncode'] == 0 for dep in j.get('needs', []))), None)
            if ready is None:
                break
            pending.remove(ready)
            active[ready['name']] = asyncio.create_task(run(ready))
        if pending and not active and all(j.get('needs') for j in pending):
            for job in pending:
                record({'event': 'not_started', 'name': job['name'], 'status': 'PREREQUISITE'})
            pending.clear()
    (OUT / 'evidence/scheduler.json').write_text(json.dumps(
        {'results': results, 'max_active': maximum, 'deadline_utc': DEADLINE.isoformat()}, indent=2) + '\n')

asyncio.run(main())
