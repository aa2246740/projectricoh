"""Fresh DAT re-check, preserving source bytes and cleaning its temporary copy."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import runpy
import shutil
import signal
import subprocess
import sys
import time
import traceback

BUNDLE = Path(__file__).resolve().parent
WORKTREE = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5')
HEAD = '652847c0ea570ba4bc1e5e635055e3a1543ec996'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=['independent-dat', 'r4-dat-root', 'r4-dat-variants', 'r4-card-extra'], default='r4-dat-variants')
    p.add_argument('--run-name', default=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S'))
    a = p.parse_args()
    assert re.fullmatch('[a-zA-Z0-9_-]+', a.run_name)
    os.setpriority(os.PRIO_PROCESS, 0, max(10, os.getpriority(os.PRIO_PROCESS, 0)))
    disk = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType'] == 'apfs' and disk['WritableVolume']
    def git(*args):
        return subprocess.check_output(['git', '--no-optional-locks', '-C', str(WORKTREE), *args], text=True)
    assert git('rev-parse', 'HEAD').strip() == HEAD
    before = git('status', '--porcelain=v1', '--untracked-files=all')
    manifest = json.loads((BUNDLE/'source-before.json').read_text())
    assert all(hashlib.sha256((WORKTREE/n).read_bytes()).hexdigest() == h for n, h in manifest.items())
    output = BUNDLE/'reproductions'/a.run_name
    assert not TMP.exists() and not output.exists(), 'A new run name and an unused temporary root are required'
    TMP.mkdir(parents=True)
    output.mkdir(parents=True)
    for name in ['source', 'home', 'tmp', 'fixtures', 'cache', 'config', 'data']:
        (TMP/name).mkdir()
    for name in manifest:
        target = TMP/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKTREE/name, target)
    os.environ['REVIEW_R5_OUTPUT'] = str(output)
    sys.path.insert(0, str(BUNDLE))
    entry = BUNDLE/('dat_identity.py' if a.case == 'independent-dat' else 'replay.py')
    sys.argv = [str(entry)] + ([] if a.case == 'independent-dat' else [a.case])
    started = time.monotonic()
    error = None
    try:
        try:
            runpy.run_path(str(entry), run_name='__main__')
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        (output/'exception.log').write_text(traceback.format_exc())
    finally:
        signal.alarm(0)
        from gxr_studio import audit
        for root in audit.protected_roots():
            if Path(root).is_relative_to(TMP):
                audit.unprotect(root)
        os.chdir(BUNDLE)
        shutil.rmtree(TMP)
    changed = [n for n, h in manifest.items() if hashlib.sha256((WORKTREE/n).read_bytes()).hexdigest() != h]
    receipt = {'head': HEAD, 'case': a.case, 'error': error, 'seconds': time.monotonic()-started,
               'nice': os.getpriority(os.PRIO_PROCESS, 0), 'source_changes': changed,
               'git_state_unchanged': git('status', '--porcelain=v1', '--untracked-files=all') == before,
               'temporary_root_removed': not TMP.exists()}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))
    return int(bool(error or changed or not receipt['git_state_unchanged']))


if __name__ == '__main__':
    raise SystemExit(main())
