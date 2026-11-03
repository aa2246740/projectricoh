"""Read-only project inputs and task-confined calibration outputs."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
CAP = ROOT / 'captures/a12-50/2026-10-24/chart-v2-R8051229-1311'
EXCHANGE = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/mount'
V6 = ROOT / 'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL'
os.environ['TMPDIR'] = str(LOCAL / 'tmp')
sys.path.insert(0, str(ROOT / 'research/module_adapt'))
import support as s
s.HERE, s.LOCAL = HERE, LOCAL
s.guard()
(LOCAL / 'tmp').mkdir(exist_ok=True)


def audit(event, args):
    if event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        targets=args[:2] if event=='os.rename' else args[:1]
        for value in targets:
            if not Path(os.fsdecode(value)).resolve().is_relative_to(HERE):
                raise PermissionError('mutation outside mount_calib_r1: '+str(value))
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        if str(path).startswith('/Volumes/') and not path.is_relative_to(ROOT):
            raise PermissionError('read outside named checkout: ' + str(path))
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not path.is_relative_to(HERE):
            raise PermissionError('write outside mount_calib_r1: ' + str(path))


sys.addaudithook(audit)
import numpy as np
import calibrate
from unit_model import UnitModel


def dump(name, value):
    s.dump(LOCAL / name, value)


def read(name):
    return s.read(LOCAL / name)


def load(name, relative):
    return s.load(name, ROOT / relative)


def model():
    m = UnitModel('mount', iso=200)
    assert s.digest(V6) == '21159c8143a87680b624adfae6b34e8ab4b4d730a8720907cf2e448dd43b1592'
    _, surface = m.base.src.surface_bank()
    entries = m.base.src.parse(s.source(V6).read_bytes(), surface)
    m.base.entries = {f'{e["slot"]:02d}': e for e in entries}
    return m


def tiff_reader():
    a = load('mount_readonly_tiff', 'research/closed_loop/local/vendor/research/color_calibration/analyze_capture.py')
    session = load('mount_session_io', 'research/chart_session_20261024/session_runtime.py')
    session.patch_tiff(a.Tiff)
    return a
