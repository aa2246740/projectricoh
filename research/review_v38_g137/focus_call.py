import builtins
import importlib.util
import io
import json
import os
import pathlib
import runpy
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v38_g137'
SOURCE = ROOT / 'research/emptystack_v38'
job, script = sys.argv[1:3]
WORK = OUT / 'local/jobs' / job
WORK.mkdir(parents=True, exist_ok=True)
LOCAL = WORK / 'local'
LOCAL.mkdir(exist_ok=True)
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v38-g137') / job
TEMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(TEMP)
tempfile.tempdir = str(TEMP)
raw_stat, raw_mkdir, raw_os_open = os.stat, os.mkdir, os.open
raw_open, raw_io_open = builtins.open, io.open
raw_run_path, raw_spec = runpy.run_path, importlib.util.spec_from_file_location
raw_popen = subprocess.Popen

def location(file, write=False):
    if not isinstance(file, (str, bytes, os.PathLike)):
        return file
    path = Path(os.path.abspath(os.fsdecode(file)))
    for prefix in (WORK/'local/tmp', SOURCE/'local/tmp'):
        try:
            return str(TEMP/path.relative_to(prefix))
        except ValueError:
            pass
    if not write:
        try:
            raw_stat(path)
        except FileNotFoundError:
            try:
                prior = SOURCE / path.relative_to(WORK)
                raw_stat(prior)
                return str(prior)
            except (ValueError, FileNotFoundError):
                pass
    try:
        tail = path.relative_to(SOURCE)
    except ValueError:
        return file
    if not write and path.suffix == '.py':
        return file
    candidate = WORK / tail
    if write:
        return str(candidate)
    try:
        raw_stat(candidate)
        return str(candidate)
    except FileNotFoundError:
        return file

def opening(original, file, mode='r', *args, **kwargs):
    return original(location(file, any(v in str(mode) for v in 'wax+')), mode, *args, **kwargs)

builtins.open = lambda file, mode='r', *args, **kwargs: opening(raw_open, file, mode, *args, **kwargs)
io.open = lambda file, mode='r', *args, **kwargs: opening(raw_io_open, file, mode, *args, **kwargs)
os.open = lambda file, flags, *args, **kwargs: raw_os_open(location(file, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))), flags, *args, **kwargs)
os.mkdir = lambda file, *args, **kwargs: raw_mkdir(location(file, True), *args, **kwargs)
os.stat = lambda file, *args, **kwargs: raw_stat(location(file), *args, **kwargs)
pathlib._normal_accessor.open = os.open
pathlib._normal_accessor.mkdir = os.mkdir
pathlib._normal_accessor.stat = os.stat
runpy.run_path = lambda file, *args, **kwargs: raw_run_path(location(file), *args, **kwargs)
importlib.util.spec_from_file_location = lambda name, file, *args, **kwargs: raw_spec(name, location(file), *args, **kwargs)

def process(command, *args, **kwargs):
    if isinstance(command, (list, tuple)):
        command = list(command)
        for i, value in enumerate(command):
            if i and str(command[i-1]) == '-o':
                command[i] = str(location(value, True))
                continue
            if isinstance(value, (str, Path)):
                text = str(value)
                if text.startswith('-I') and len(text) > 2:
                    command[i] = '-I' + str(location(text[2:]))
                elif text.startswith('/'):
                    command[i] = str(location(text))
        if command and ('python' in Path(command[0]).name.lower() or Path(command[0]).name == 'Python'):
            command[0] = '/usr/bin/python3'
            if '-I' not in command:
                command.insert(1, '-I')
            if '-B' not in command:
                command.insert(1, '-B')
            for i, value in enumerate(command[1:], 1):
                candidate=Path(str(value))
                if candidate.parent==SOURCE and candidate.suffix=='.py':
                    command=['/usr/bin/python3','-I','-B',str(OUT/'focus_call.py'),job,
                             candidate.name,*command[i+1:]]
                    break
    return raw_popen(command, *args, **kwargs)

subprocess.Popen = process
sys.path.insert(0, str(SOURCE))
target = SOURCE / script
sys.argv = [str(target), *sys.argv[3:]]
def setup_trace(frame, event, arg):
    if str(frame.f_code.co_filename).startswith(str(SOURCE)):
        os.environ['TMPDIR'] = str(TEMP)
        tempfile.tempdir = str(TEMP)
    if str(frame.f_code.co_filename).startswith(str(SOURCE)) and frame.f_code.co_name == '<module>':
        if 'ROOT' in frame.f_globals:
            frame.f_globals['ROOT'] = ROOT
        if 'WORK' in frame.f_globals:
            frame.f_globals['WORK'] = WORK
        if 'LOCAL' in frame.f_globals:
            frame.f_globals['LOCAL'] = LOCAL
        if 'HERE' in frame.f_globals and Path(frame.f_code.co_filename).name == 'run_existing.py':
            frame.f_globals['HERE'] = WORK
    return setup_trace if str(frame.f_code.co_filename).startswith(str(SOURCE)) else None

sys.settrace(setup_trace)
code = 0
try:
    runpy.run_path(str(target), run_name='__main__')
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
except BaseException as exc:
    code = 1
    print(json.dumps({'error_type': type(exc).__name__, 'message': str(exc),
        'frames': [{'file': f.filename, 'line': f.lineno, 'function': f.name}
                   for f in traceback.extract_tb(exc.__traceback__)]}), flush=True)
finally:
    sys.settrace(None)
sys.exit(code)
