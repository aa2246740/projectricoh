"""One event-driven queue with a lock and at most three simulation slots (runs the fenced runner commands from plan.json and queue-additions.json)."""
from pathlib import Path
import asyncio
import datetime
import fcntl
import json
import os
import signal
import time

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent

async def main():
    lock = (WORK / 'local/scheduler.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = json.loads((WORK / 'plan.json').read_text())
    deadline = datetime.datetime.fromisoformat(plan['deadline_utc']).timestamp()
    active, complete, queue = {}, [], list(plan['jobs'])
    wake = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, wake.set)
    known = {job['name'] for job in queue}
    events = (WORK / 'runs.jsonl').open('a', buffering=1)

    async def run(job):
        start = time.time()
        command = ['/usr/bin/sandbox-exec', '-f', str(WORK / 'write-fence.sb'), '/usr/bin/python3', '-I', '-B', *job['args']]
        env = {**os.environ, 'TMPDIR': str(WORK / 'local/tmp'), 'PYTHONDONTWRITEBYTECODE': '1', 'GIT_OPTIONAL_LOCKS': '0'}
        process = await asyncio.create_subprocess_exec(*command, cwd=str(ROOT), env=env, stdout=asyncio.subprocess.PIPE,
                                                       stderr=asyncio.subprocess.PIPE, start_new_session=True)
        events.write(json.dumps({'name': job['name'], 'event': 'STARTED', 'pid': process.pid,
                                 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}) + '\n')
        state = 'FINISHED'
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(),
                                                    timeout=min(plan['timeout_seconds'], max(1, deadline - time.time())))
        except asyncio.TimeoutError:
            state = 'TIMEBOX' if time.time() >= deadline - 2 else 'TIMEOUT'
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
            except asyncio.TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = await process.communicate()
        folder = WORK / 'local/logs'
        folder.mkdir(exist_ok=True)
        (folder / (job['name'] + '.out')).write_bytes(stdout[-20000:])
        (folder / (job['name'] + '.err')).write_bytes(stderr[-20000:])
        result = {'name': job['name'], 'kind': job['kind'], 'returncode': process.returncode, 'state': state,
                  'seconds': round(time.time() - start, 3), 'stdout_lines': len(stdout.splitlines()), 'stderr_lines': len(stderr.splitlines())}
        events.write(json.dumps(result) + '\n')
        complete.append(result)
        (WORK / 'schedule-results.json').write_text(json.dumps(complete, indent=1) + '\n')
        return result

    while queue or active:
        capacity_file = WORK / 'capacity.json'
        capacity = json.loads(capacity_file.read_text())['workers'] if capacity_file.exists() else plan['workers']
        assert 1 <= capacity <= 3
        additions = WORK / 'queue-additions.json'
        if additions.exists():
            for job in json.loads(additions.read_text()):
                if job['name'] not in known:
                    known.add(job['name'])
                    queue.append(job)
        while queue and len(active) < capacity and time.time() < deadline:
            job = queue.pop(0)
            active[asyncio.create_task(run(job))] = job['name']
        (WORK / 'schedule-state.json').write_text(json.dumps({'active': list(active.values()), 'finished': len(complete),
            'remaining': [j['name'] for j in queue], 'pid': os.getpid(), 'capacity': capacity}, indent=1) + '\n')
        if not active:
            if queue and time.time() >= deadline:
                break
            await asyncio.sleep(5)
            if not queue:
                break
            continue
        listener = asyncio.create_task(wake.wait())
        done, _ = await asyncio.wait([*active, listener], return_when=asyncio.FIRST_COMPLETED, timeout=60)
        if listener in done:
            done.remove(listener)
            wake.clear()
        else:
            listener.cancel()
        for task in done:
            task.result()
            active.pop(task)
    for job in queue:
        complete.append({'name': job['name'], 'kind': job['kind'], 'state': 'NOT_STARTED', 'returncode': None, 'seconds': 0})
    (WORK / 'schedule-results.json').write_text(json.dumps(complete, indent=1) + '\n')
    print(json.dumps({'name': 'schedule_finished', 'finished': len(complete), 'not_started': len(queue)}), flush=True)

if __name__ == '__main__':
    asyncio.run(main())
