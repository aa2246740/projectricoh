"""Remove only this review's temporary directory and record remaining review processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch-r3')


def main():
    assert not TMP.is_symlink() and TMP.resolve() == TMP
    before = [str(path.relative_to(TMP)) for path in sorted(TMP.rglob('*'))] if TMP.exists() else []
    if TMP.exists():
        shutil.rmtree(TMP)
    rows = subprocess.run(['/bin/ps', '-axo', 'pid=,ni=,comm=,args='],
                          check=True, capture_output=True, text=True).stdout.splitlines()
    remaining = []
    for row in rows:
        fields = row.split(None, 3)
        if len(fields) != 4:
            continue
        pid, nice, command, arguments = fields
        if int(pid) != os.getpid() and 'python' in Path(command).name.lower() and \
                'review_emulator_batch_r3/' in arguments:
            remaining.append({'pid': int(pid), 'nice': int(nice), 'command': arguments})
    result = {'tmpdir': str(TMP), 'contents_before_cleanup': before,
              'tmpdir_removed': not TMP.exists(), 'remaining_review_python_processes': remaining,
              'passed': not TMP.exists() and not remaining}
    (HERE / 'local/cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    assert result['passed']


if __name__ == '__main__':
    main()
