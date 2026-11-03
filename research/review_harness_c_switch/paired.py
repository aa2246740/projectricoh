from pathlib import Path
import datetime
import json
import os
import resource
import subprocess
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch')


def main():
    jobs = json.loads((OUT / 'selected-queue.json').read_text())['jobs']
    (OUT / 'paired').mkdir(exist_ok=False)
    records = []
    for index, job in enumerate(jobs):
        queue = OUT / 'paired' / (job['name'] + '.json')
        queue.write_text(json.dumps({'jobs': [job]}, indent=2) + '\n')
        sides = ('python', 'c') if index % 2 == 0 else ('c', 'python')
        for side in sides:
            name = 'extra-' + side + '-' + job['name']
            folder = OUT / 'entry/local/runs' / name
            if folder.exists():
                raise FileExistsError(folder)
            env = dict(os.environ, TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1')
            for key in list(env):
                if key.startswith('GXR_HARNESS_') or key in ('GXR_CCORE_BUILD_MANIFEST', 'GXR_HOST_METRICS_DIR'):
                    env.pop(key)
            if side == 'c':
                env['GXR_HARNESS_BACKEND'] = 'c'
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            started = time.monotonic()
            command = ['/usr/bin/sandbox-exec', '-f', str(OUT / 'fence.sb'),
                       '/usr/bin/python3', '-I', '-B', str(OUT / 'entry/run.py'),
                       '--name', name, '--queue', str(queue), '--slots', '1']
            log = OUT / 'paired' / (name + '.log')
            timeout = max(10800, 3 * max([job.get('historical_seconds') or 0,
                                         *job.get('g139_seconds', {}).values()]))
            event = {'event': 'start', 'job': job['name'], 'side': side,
                     'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'command': command, 'timeout_seconds': timeout}
            print(json.dumps(event), flush=True)
            with log.open('wb') as stream:
                try:
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=timeout)
                    code = result.returncode
                    execution = 'FINISHED'
                except subprocess.TimeoutExpired:
                    code = None
                    execution = 'TIMEOUT'
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            record = dict(event, event='finish', returncode=code, execution=execution,
                          wall_seconds=time.monotonic() - started,
                          cpu_seconds=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                          load_end=os.getloadavg(), nice=os.getpriority(os.PRIO_PROCESS, 0),
                          folder=str(folder), log=str(log))
            records.append(record)
            (OUT / 'paired/progress.json').write_text(json.dumps(records, indent=2) + '\n')
            print(json.dumps(record), flush=True)
            if execution != 'FINISHED':
                raise RuntimeError('Time limit reached')
    (OUT / 'paired/complete.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
