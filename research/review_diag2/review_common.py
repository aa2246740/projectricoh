"""Paths, output limits, and compact result files for this review."""
from pathlib import Path
import hashlib
import json
import os
import signal
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DAT = ROOT / 'firmware/package_v36_diag2/local/SD_ROOT/GXRCE.DAT'
DAT_SHA = 'ef39f71b9e8df800cffd7998474668f992534e71807e55a92f2146c375f0ede4'


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            value.update(chunk)
    return value.hexdigest()


def save(name, value):
    path = (HERE / name).resolve()
    if HERE not in path.parents:
        raise RuntimeError('OUTPUT_LIMIT')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, int) or not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return
        paths = [path]
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
        paths = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths = list(args[:2])
    for item in paths:
        path = Path(item).resolve()
        if path != HERE and HERE not in path.parents:
            raise RuntimeError('OUTPUT_LIMIT')


def start():
    sys.addaudithook(fence)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(1800)
    LOCAL.mkdir(parents=True, exist_ok=True)
    if sha(DAT) != DAT_SHA:
        raise RuntimeError('DAT_IDENTITY')
    os.environ['TMPDIR'] = str(LOCAL)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['CLANG_MODULE_CACHE_PATH'] = str(LOCAL / 'modules')
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def fail(name, error):
    frames = []
    current = error.__traceback__
    while current:
        frames.append({'file': Path(current.tb_frame.f_code.co_filename).name,
                       'line': current.tb_lineno})
        current = current.tb_next
    save(name + '-error.json', {'type': type(error).__name__, 'frames': frames})
    print(name, 'RETURN 1 TYPE', type(error).__name__, flush=True)

