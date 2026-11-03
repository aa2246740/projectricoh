"""Run research/emptystack_v38/empty_check.py (by path, unchanged) against gen 139.

Its `scope` and `accept` imports are bound to this task: outputs go to
research/g139_fix/es/local, the boot uses the g139 package, and the
normal-boot fixture (../fixture.py) is installed. /usr/bin/python3 -I -B.
  empty_call.py <50mm|28mm|mount>
"""
from pathlib import Path
import hashlib
import json
import os
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'run'))
sys.path.insert(0, str(HERE.parent / 'tests'))
import fixture
import g139_host as g138_host

fixture.install()
scope = types.ModuleType('scope')
scope.ROOT, scope.WORK, scope.LOCAL = ROOT, HERE, HERE / 'local'


def setup():
    sys.dont_write_bytecode = True
    scope.LOCAL.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(g138_host.TMP), PYTHONDONTWRITEBYTECODE='1')


def save(path, value):
    path = Path(path)
    path.resolve().relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


scope.setup, scope.save = setup, save
scope.sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
sys.modules['scope'] = scope
accept = types.ModuleType('accept')
accept.module = g138_host.accept_module
sys.modules['accept'] = accept
g138_host.setup()
target = ROOT / 'research/emptystack_v38/empty_check.py'
sys.argv = [str(target), *sys.argv[1:]]
runpy.run_path(str(target), run_name='__main__')
