"""Complete the review checks in one sequence, with no parallel workers."""
from pathlib import Path
import json
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_call
import scope


def main():
    sys.addaudithook(legacy_call.fence)
    dat = scope.ROOT/'firmware/package_v36_diag2/local/SD_ROOT/GXRCE.DAT'
    digest = scope.sha(dat)
    jobs = []
    for unit in ('50mm', '28mm', 'mount'):
        jobs.append(('errors-'+unit, ['errors', '--unit', unit]))
        for kind in ('prepublish', 'preserve', 'withdrawal'):
            jobs.append((kind+'-'+unit, ['probes', '--unit', unit, '--kind', kind]))
    jobs.extend((('reopen-50mm', ['probes', '--unit', '50mm', '--kind', 'reopen']),
                 ('first-service-50mm', ['probes', '--unit', '50mm', '--kind', 'first_service_failure'])))
    output = scope.HERE/'review-extra-r2.json'
    previous = json.loads(output.read_text()) if '--resume' in sys.argv and output.exists() else {}
    records = previous.get('jobs', [])
    if records:
        assert previous['dat_sha256'] == digest
    done = {item['name'] for item in records if item['returncode'] == 0}
    records = [item for item in records if item['returncode'] == 0]
    for name, arguments in jobs:
        if name in done:
            continue
        scope.freeze_check()
        assert scope.sha(dat) == digest
        started = time.monotonic()
        result = subprocess.run(['/usr/bin/python3', '-I', '-B', str(scope.HERE/'suite_r2.py'),
            'research/review_diag/replay.py'] + arguments, cwd=scope.ROOT,
            capture_output=True, text=True, timeout=3600)
        records.append(dict(name=name, original_path='research/review_diag/replay.py',
                            arguments=arguments, returncode=result.returncode,
                            seconds=round(time.monotonic()-started, 3)))
        scope.save(output, dict(status='RUNNING' if result.returncode == 0 else 'FAIL',
                               dat_sha256=digest, jobs=records))
        print(name, 'RETURN', result.returncode, 'COUNT 1', flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    scope.save(output, dict(status='PASS', dat_sha256=digest, jobs=records))
    print('REVIEW_EXTRA_R2 RETURN 0 COUNT', len(records), flush=True)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:
        print('REVIEW_EXTRA_R2 RETURN 1 COUNT 0 TYPE', type(error).__name__)
        raise SystemExit(1)
