"""Run one offline foreground job, with a timeout and fresh-output receipts.

g150 copy of research/review_g139/run_case.py. --generation 139|150 selects the
engine tree and packages under test; receipts and logs go to research/g150.
"""
from pathlib import Path
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import plistlib
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g150')
TARGETS = {139: ('firmware/engine_v56_g139', 'firmware/package_v38_g139', 'firmware/package_v38_g139_test'),
           150: ('firmware/engine_v58_g150', 'firmware/package_v38_g150', 'firmware/package_v38_g150_test')}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True)
    parser.add_argument('--timeout', type=int, default=7200)
    parser.add_argument('--outputs', nargs='*', default=[])
    parser.add_argument('--generation', type=int, choices=(139, 150), required=True)
    parser.add_argument('--package', choices=('release', 'test'), default='test')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command and args.command[0] == '--'
    command = args.command[1:]
    assert command and '/' in command[0]
    receipts = HERE / 'evidence/receipts'
    receipts.mkdir(parents=True, exist_ok=True)
    receipt = receipts / (args.job + '.json')
    log = HERE / 'evidence' / (args.job + '.log')
    assert not receipt.exists() and not log.exists(), 'use a new job name'
    outputs = [ROOT / p for p in args.outputs]
    for path in outputs:
        assert path.resolve().is_relative_to(HERE)
        assert not path.exists(), 'existing output is not a fresh result'
    # Two slots shared by all runners. Each child runs sequentially in its slot.
    handles = []
    slot = None
    for i in range(2):
        stream = (HERE / ('slot-%d.lock' % i)).open('a')
        handles.append(stream)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            slot = i
            break
        except BlockingIOError:
            pass
    assert slot is not None, 'two test jobs are already running'
    started_ns = time.time_ns()
    started = time.monotonic()
    engine, release, test = TARGETS[args.generation]
    environment = dict(os.environ, TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1',
                       REVIEW_JOB=args.job, G139_PACKAGE=test if args.package == 'test' else release,
                       G139_ENGINE=engine, G150_RELEASE_PACKAGE=release, G150_TEST_PACKAGE=test)
    env_keys = ('TMPDIR', 'PYTHONDONTWRITEBYTECODE', 'REVIEW_JOB', 'G139_PACKAGE', 'G139_ENGINE',
                'G150_RELEASE_PACKAGE', 'G150_TEST_PACKAGE')
    result = dict(job=args.job, slot=slot, started_ns=started_ns,
                  started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  command=command, timeout_seconds=args.timeout,
                  environment={key: environment[key] for key in env_keys},
                  dat_sha256=digest(ROOT / environment['G139_PACKAGE'] / 'local/SD_ROOT/GXRCE.DAT'),
                  engine_sha256=digest(ROOT / engine / 'candidate/local/full-r13/engine.elf'))
    result['review_scripts'] = {str(path.relative_to(ROOT)): digest(path) for path in HERE.rglob('*.py')
                               if 'local' not in path.relative_to(HERE).parts}
    mount = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert mount['MountPoint']=='/Volumes/Workspace' and mount['FilesystemType']=='apfs'
    assert mount['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and mount['WritableVolume'] and mount['WritableMedia']
    (HERE/'evidence/mount').mkdir(exist_ok=True)
    attestation=dict(uuid=mount['VolumeUUID'],filesystem=mount['FilesystemType'],mount=mount['MountPoint'],
                     device=os.stat('/Volumes/Workspace').st_dev,observed_ns=time.time_ns())
    (HERE/'evidence/mount'/(args.job+'.json')).write_text(json.dumps(attestation,indent=2)+'\n')
    result['mount']=attestation
    with log.open('wb') as stream:
        process = subprocess.Popen(['/usr/bin/nice', '-n', '10', '/usr/bin/sandbox-exec', '-f',
                                    str(HERE / 'offline.sb'), *command], cwd=ROOT, env=environment,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            import select
            queue = select.kqueue()
            event = select.kevent(process.pid, filter=select.KQ_FILTER_PROC, flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT, fflags=select.KQ_NOTE_EXIT)
            events = queue.control([event], 1, args.timeout)
            queue.close()
            if not events:
                raise subprocess.TimeoutExpired(command, args.timeout)
            process.wait()
            result['returncode'] = process.returncode
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            result['returncode'] = 'TIMEOUT'
    result['seconds'] = round(time.monotonic() - started, 3)
    result['ended_ns'] = time.time_ns()
    result['outputs'] = []
    for path in outputs:
        row = dict(path=str(path.relative_to(ROOT)), exists=path.is_file())
        if path.is_file():
            stat = path.stat()
            row.update(size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=digest(path),
                       fresh=stat.st_mtime_ns >= started_ns)
            if path.suffix == '.json':
                data = json.loads(path.read_text())
                row.update(status=data.get('status'), case_seconds=data.get('seconds'),
                           dat_sha256=data.get('dat_sha256'))
        result['outputs'].append(row)
    states=[r.get('status','PASS') for r in result['outputs']]
    complete=result['returncode']==0 and all(r.get('fresh') for r in result['outputs'])
    if complete and all(isinstance(s,str) and s.startswith(('PASS','OBSERVED')) for s in states):
        result['status']='OBSERVED' if any(s.startswith('OBSERVED') for s in states) else 'PASS'
    else:
        result['status']='FAIL'
    result['log_sha256'] = digest(log)
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    shown = {key: result[key] for key in ('job','status','returncode','seconds')}
    shown['outputs'] = [{key: row.get(key) for key in ('path','status','fresh')} for row in result['outputs']]
    print(json.dumps(shown), flush=True)
    raise SystemExit(0 if result['status'] in ('PASS','OBSERVED') else 1)

if __name__ == '__main__':
    main()
