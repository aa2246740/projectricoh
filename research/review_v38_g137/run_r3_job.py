# Runs the implementation round's own single-job wrapper by path (no copy).
# Every write that would land in research/emptystack_v38 is redirected into this
# review's job directory, so the implementer's evidence is never overwritten.
# Reads prefer a redirected copy when one exists (read-after-write stays coherent).
import builtins
import io
import os
import pathlib
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v38_g137'
SOURCE = ROOT / 'research/emptystack_v38'
TARGET = SOURCE / 'r3_job.py'
name = sys.argv[1]
SHADOW = OUT / 'local/jobs' / name / 'es'
SHADOW.mkdir(parents=True, exist_ok=True)
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v38-g137') / name
TEMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(TEMP)
raw_open, raw_io_open, raw_os_open = builtins.open, io.open, os.open
raw_mkdir, raw_stat, raw_replace, raw_rename, raw_unlink = os.mkdir, os.stat, os.replace, os.rename, os.unlink

def shadow(file, write):
    if not isinstance(file, (str, bytes, os.PathLike)):
        return file
    path = Path(os.path.abspath(os.fsdecode(file)))
    try:
        tail = path.relative_to(SOURCE)
    except ValueError:
        return file
    if path.suffix == '.py' and not write:
        return file
    target = SHADOW / tail
    if write:
        os.makedirs(target.parent, exist_ok=True)
        return str(target)
    try:
        raw_stat(target)
        return str(target)
    except FileNotFoundError:
        return file

def writes(mode):
    return any(c in str(mode) for c in 'wax+')

builtins.open = lambda f, mode='r', *a, **k: raw_open(shadow(f, writes(mode)), mode, *a, **k)
io.open = lambda f, mode='r', *a, **k: raw_io_open(shadow(f, writes(mode)), mode, *a, **k)
os.open = lambda f, flags, *a, **k: raw_os_open(shadow(f, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))), flags, *a, **k)
os.mkdir = lambda f, *a, **k: raw_mkdir(shadow(f, True), *a, **k)
os.stat = lambda f, *a, **k: raw_stat(shadow(f, False), *a, **k)
os.replace = lambda a, b, *x, **k: raw_replace(shadow(a, False), shadow(b, True), *x, **k)
os.rename = lambda a, b, *x, **k: raw_rename(shadow(a, False), shadow(b, True), *x, **k)
os.unlink = lambda f, *a, **k: raw_unlink(shadow(f, True), *a, **k)
pathlib._normal_accessor.open = os.open
pathlib._normal_accessor.mkdir = os.mkdir
pathlib._normal_accessor.stat = os.stat
pathlib._normal_accessor.replace = os.replace
pathlib._normal_accessor.rename = os.rename
pathlib._normal_accessor.unlink = os.unlink
sys.argv = [str(TARGET), name]
runpy.run_path(str(TARGET), run_name='__main__')
