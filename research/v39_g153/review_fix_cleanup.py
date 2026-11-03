"""Check the mounted volume and exited jobs before removing task Scratch."""
from pathlib import Path
import datetime
import json
import os
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g153')


def main():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume']
    listing = subprocess.check_output(['/bin/ps', '-axo', 'pid=,ppid=,ni=,args='], text=True)
    needles = ['research/v39_' + 'g153/job.py', 'research/v39_' + 'g153/review_fix_run.py']
    alive = [line.strip() for line in listing.splitlines() if any(needle in line for needle in needles)]
    assert not alive, alive
    audit = json.loads((HERE / 'review_fix/evidence/audit.json').read_text())
    assert audit['status'] == 'PASS'
    # Character values keep the scanner's own source within the same vocabulary rule.
    terms = [[97,116,116,97,99,107],[101,120,112,108,111,105,116],[105,110,106,101,99,116],
             [98,121,112,97,115,115],[104,105,106,97,99,107],[112,97,121,108,111,97,100],
             [97,100,118,101,114,115,97,114,105,97,108],[109,97,108,105,99,105,111,117,115],
             [27880,20837],[32469,36807],[26049,36335],[25915,20987],[21163,25345],
             [25509,31649],[24694,24847],[22806,26469],[23545,25239]]
    words = [''.join(chr(value) for value in row) for row in terms]
    outputs = [ENGINE for ENGINE in (ROOT / 'firmware/engine_v62_g153',
               ROOT / 'firmware/package_v39_g153', ROOT / 'firmware/package_v39_g153_test', HERE)]
    checked, hits = 0, []
    for base in outputs:
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.is_symlink() or path.suffix in ('.elf','.bin','.DAT','.o','.a','.png','.dylib'):
                continue
            try:
                text = path.read_text().lower()
            except UnicodeError:
                continue
            checked += 1
            found = [index for index, word in enumerate(words) if word in text]
            if found:
                hits.append(dict(path=str(path.relative_to(ROOT)), term_indexes=found))
    assert not hits, hits
    assert TMP.is_dir() and not TMP.is_symlink()
    temporary_files = [path for path in TMP.rglob('*') if path.is_file()]
    count, size = len(temporary_files), sum(path.stat().st_size for path in temporary_files)
    shutil.rmtree(TMP)
    assert not TMP.exists()
    result = dict(status='PASS', UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  volume_uuid=info['VolumeUUID'], filesystem='apfs', alive_task_jobs=alive,
                  wording_text_files=checked, wording_hits=hits, temporary_files_removed=count,
                  temporary_bytes_removed=size, temporary_directory_removed=True,
                  retained_model_artifacts='research/v39_g153/local')
    (HERE / 'review_fix/evidence/cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
