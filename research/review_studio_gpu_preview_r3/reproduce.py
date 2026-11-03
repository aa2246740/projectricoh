"""Fresh, bounded reproduction entry. It writes only below the named Scratch root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import time

BUNDLE = Path(__file__).resolve().parent
WT = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
FENCE = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3')
HEAD = 'f47572e6ac524400b79f6bebf986be368525e0a6'
CASES = ['extra', 'windows-contracts', 'windows-loop-guard', 'media_root_race', 'path_delete_race',
         'card_reader_retarget', 'lut_reimport_probe', 'http_boundary_extra']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=CASES, default='extra')
    p.add_argument('--run-name', default='fresh-reproduction')
    a = p.parse_args()
    assert re.fullmatch('[a-z0-9_-]+', a.run_name), 'Use a plain, fresh run name'
    disk = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'] == 'apfs' and disk['WritableVolume'] and disk['MountPoint'] == '/Volumes/Workspace'
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS':'0', 'PYTHONDONTWRITEBYTECODE':'1'}
    actual = subprocess.check_output(['git','rev-parse','HEAD'], cwd=WT, env=env, text=True).strip()
    assert actual == HEAD, 'The checkout no longer matches the reviewed revision'
    run = FENCE / a.run_name
    assert not run.exists(), 'Refusing an existing run name'
    run.mkdir(parents=True)
    source, results = run / 'source', run / 'results'
    source.mkdir(); results.mkdir()
    manifest = json.loads((BUNDLE / 'source-before.json').read_text())
    for name, expected in manifest.items():
        data = (WT / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, name
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in ('home','tmp','cache'):(run / name).mkdir()
    env.update(HOME=str(run/'home'), TMPDIR=str(run/'tmp'), TMP=str(run/'tmp'), TEMP=str(run/'tmp'),
               XDG_CACHE_HOME=str(run/'cache'), REVIEW_TMP=str(run), REVIEW_SOURCE=str(source), REVIEW_OUT=str(results),
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    script = {'extra':'extra_boundaries.py','windows-contracts':'windows_contracts.py','windows-loop-guard':'windows_loop_guard.py'}.get(a.case, 'replay_r2.py')
    command = [str(WT/'.venv/bin/python'),'-I','-B',str(BUNDLE/script)]
    if script == 'replay_r2.py':command.append(a.case)
    os.setpriority(os.PRIO_PROCESS, 0, max(10, os.getpriority(os.PRIO_PROCESS, 0)))
    started = time.monotonic()
    result = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True, timeout=300)
    (results/'stdout.log').write_text(result.stdout)
    (results/'stderr.log').write_text(result.stderr)
    receipt = {'head':HEAD,'case':a.case,'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started,'results':str(results),'tracked_sources_changed':any(hashlib.sha256((WT/n).read_bytes()).hexdigest()!=h for n,h in manifest.items())}
    (results/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(result.stdout)
    print(json.dumps(receipt))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
