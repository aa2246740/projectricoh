#!/usr/bin/python3 -I
"""Run one retained regression group with isolated writes and batch execution."""
from pathlib import Path
import os
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_model as B

sys.path.insert(0, str(B.ROOT / 'tools/native_harness'))
import python_backend
python_backend.PythonBackend = B.ModelBackend

original_exit = os._exit


def recorded_exit(code):
    B.save_stats(str(os.getpid()))
    return original_exit(code)


os._exit = recorded_exit

source_path = B.ROOT / 'research/body_v39/regress/run/legacy_call.py'
source = source_path.read_text()
output = B.OUT / 'regression-run'
output.mkdir(exist_ok=True)
old = "OUT = ROOT / 'research/body_v39/regress/run'"
assert source.count(old) == 1
source = source.replace(old, 'OUT = Path(' + repr(str(output)) + ')')
old = "SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/body-v39/legacy')"
assert source.count(old) == 1
source = source.replace(old, 'SCRATCH = Path(' + repr(os.environ['REVIEW_TEMP'] + '/legacy') + ')')
sys.argv[0] = str(source_path)
namespace = {'__name__': '__main__', '__file__': str(source_path)}
exec(compile(source, str(source_path), 'exec'), namespace)
