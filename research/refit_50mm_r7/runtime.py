"""Task-local adapters for the unchanged module_adapt calibration code."""
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for name in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['GIT_OPTIONAL_LOCKS']='0'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DATA = ROOT / 'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm'
sys.path.insert(0, str(ROOT / 'research/module_adapt'))
import support as s
s.HERE, s.LOCAL = HERE, LOCAL
s.guard()


def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, Path)):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if str(path).startswith('/Volumes/') and not path.is_relative_to(ROOT):
        raise PermissionError('read outside named checkout: ' + str(path))
    mode, flags = args[1:3]
    write = isinstance(mode, str) and any(c in mode for c in 'wax+')
    write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if write and not path.is_relative_to(HERE):
        raise PermissionError('write outside refit_50mm_r7: ' + str(path))


sys.addaudithook(audit)
import numpy as np
import calibrate
from unit_model import UnitModel


def model():
    m = UnitModel('50mm', iso=200)
    assert s.digest(s.DAILY) == '44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05'
    return m


def dump(path, value):
    s.dump(LOCAL / path, value)


def load(path):
    import json
    return json.loads((LOCAL / path).read_text())


def exchange(slot='04'):
    return calibrate.load_exchange(DATA / 'patches.jsonl', DATA / 'frames.json', '50mm', slot)[0]
