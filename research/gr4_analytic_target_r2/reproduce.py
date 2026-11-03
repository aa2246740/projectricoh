"""Foreground-only reproducible run. Cached completed fits are never recomputed."""
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'


def main():
    # The driver owns no input ledger. Each sequential child verifies and updates
    # its own ledger, avoiding a stale parent overwriting a completed child.
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia'] and not HERE.is_symlink()
    LOCAL.mkdir(exist_ok=True)
    commands = [
        ('prepare.py', []), ('fit.py', []), ('lut.py', []), ('sensitivity.py', []), ('decompose.py', []),
        ('diagnostics.py', ['--wide-radius', '--wide-sensitivity']), ('improve.py', []),
        ('verify.py', []), ('report.py', []), ('verify.py', ['--seal']),
    ]
    for index, (name, args) in enumerate(commands):
        command = [sys.executable, '-I', '-B', str(HERE / name), *args]
        logpath = LOCAL / f'reproduce_{index:02d}_{name}.log'
        with logpath.open('w') as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                log.write(line)
                print(line, end='', flush=True)
            code = process.wait()
        if code:
            raise SystemExit(f'{name} failed with code {code}; see {logpath}')


if __name__ == '__main__': main()
