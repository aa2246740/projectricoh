"""Read-only inputs, two output roots, and task-owned scratch."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'research/emulator_fast_r1'
FAST = ROOT / 'tools/gxr_emulator_fast'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-r1')


def enable():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    os.environ['TMPDIR'] = str(TEMP)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    roots = (HERE, FAST, TEMP)

    def path(value):
        if isinstance(value, (str, bytes, os.PathLike)):
            return Path(os.fsdecode(value)).resolve()
        return None

    def guard(event, args):
        if event.startswith('socket.'):
            raise PermissionError('network disabled for emulator-fast-r1')
        candidates = []
        if event == 'open':
            p = path(args[0])
            if p and str(p).startswith('/Volumes/RICOHDCX'):
                raise PermissionError('physical media disabled')
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or \
                    (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                candidates.append(p)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
            candidates.append(path(args[0]))
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            candidates.extend(path(v) for v in args[:2])
        for p in candidates:
            if p and not any(p.is_relative_to(base) for base in roots):
                raise PermissionError('write outside task roots: ' + str(p))
    sys.addaudithook(guard)
    TEMP.mkdir(exist_ok=True)
