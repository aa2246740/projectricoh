"""Run the retained 81-group matrix with two event-driven test slots (g139).

Copy of research/review_g138/run_regressions.py: output, Scratch and the
target package are this task's (G139_PACKAGE, default the g139 release).

Each job has an independent working directory, raw log and OS exit receipt.
The scheduler waits for subprocess completion; it has no timed polling loop.
"""
import argparse
import asyncio
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g139')
PACKAGE = os.environ.get('G139_PACKAGE', 'firmware/package_v38_g139')
DAT = ROOT / PACKAGE / 'local/SD_ROOT/GXRCE.DAT'
PIN = dict(reversed(l.split('  ', 1)) for l in (ROOT / PACKAGE / 'SHA256SUMS').read_text().splitlines())[str(DAT.relative_to(ROOT))]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(value):
    value['utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    with (OUT / 'evidence/runs.jsonl').open('a') as stream:
        stream.write(json.dumps(value) + '\n')
    print(json.dumps(value), flush=True)


async def run(job, semaphore):
    async with semaphore:
        receipt = OUT / 'evidence/receipts' / (job['name'] + '.json')
        if receipt.exists():
            prior = json.loads(receipt.read_text())
            assert prior['dat_sha256'] == PIN
            return prior
        assert sha(DAT) == PIN
        target = ([str(OUT / job['driver']), *job['args']] if 'driver' in job else
                  [str(OUT / 'run/legacy_call.py'), job['name'], *job['args']])
        command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'offline.sb'),
                   '/usr/bin/python3', '-I', '-B', *target]
        environment = dict(os.environ, TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1',
                           GIT_OPTIONAL_LOCKS='0', REVIEW_JOB=job['name'], G139_PACKAGE=PACKAGE)
        environment.update(job.get('env', {}))
        for name in ('REVIEW_ONLY_CASE', 'REVIEW_MENU_PROBE'):
            if name not in job.get('env', {}):
                environment.pop(name, None)
        started = time.monotonic()
        log = OUT / 'local/logs' / (job['name'] + '.log')
        with log.open('wb') as stream:
            process = await asyncio.create_subprocess_exec(
                *command, cwd=ROOT, env=environment, stdout=stream,
                stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            emit({'event': 'start', 'name': job['name'], 'pid': process.pid,
                  'timeout_seconds': job['timeout_seconds']})
            status = 'FINISHED'
            try:
                code = await asyncio.wait_for(process.wait(), job['timeout_seconds'])
            except asyncio.TimeoutError:
                status = 'TIMEOUT'
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), 8)
                except asyncio.TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
                code = process.returncode
        result = dict(job, returncode=code, execution=status,
                      seconds=round(time.monotonic() - started, 3), dat_sha256=sha(DAT),
                      command=command, log=str(log.relative_to(ROOT)),
                      log_sha256=sha(log))
        assert result['dat_sha256'] == PIN
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        emit({'event': 'finish', 'name': job['name'], 'returncode': code,
              'execution': status, 'seconds': result['seconds']})
        return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', default='queue.json')
    parser.add_argument('--slots', type=int, default=2, choices=[1, 2])
    args = parser.parse_args()
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert volume['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType'] == 'apfs' and volume['MountPoint'] == '/Volumes/Workspace'
    assert volume['WritableVolume'] and volume['WritableMedia']
    assert not TMP.is_symlink()
    TMP.mkdir(parents=True, exist_ok=True)
    assert TMP.resolve() == TMP
    assert sha(DAT) == PIN
    plan = json.loads((OUT / args.queue).read_text())
    # Keep the user-tool prerequisite separate, before any users job.
    jobs = plan['jobs']
    semaphore = asyncio.Semaphore(args.slots)
    emit({'event': 'scheduler', 'pid': os.getpid(), 'slots': args.slots,
          'jobs': len(jobs), 'queue': args.queue})
    if jobs and jobs[0]['name'] == 'user-tool':
        prerequisite = await run(jobs[0], semaphore)
        assert prerequisite['returncode'] == 0, 'user fixture prerequisite failed'
        jobs = jobs[1:]
    results = await asyncio.gather(*(run(job, semaphore) for job in jobs))
    path = OUT / 'evidence' / (Path(args.queue).stem + '-complete.json')
    path.write_text(json.dumps({'dat_sha256': PIN, 'slots': args.slots,
                                'results': results}, indent=2) + '\n')
    emit({'event': 'complete', 'jobs': len(results),
          'exit_zero': sum(row['returncode'] == 0 for row in results)})


if __name__ == '__main__':
    with (OUT / 'local/scheduler.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(main())
