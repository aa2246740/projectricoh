"""Task-local adapter over the sealed native-C040 reference and guarded solver."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import types

assert sys.flags.isolated, 'Run Python -I -B'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCAL = HERE/'local'
os.environ['GXR_C040_GEOMETRY'] = 'native'
FREEZE = json.loads((LOCAL/'freeze.json').read_text())
_owner_module = sys.modules[__name__]

# Verify the modules used below against the input freeze before importing them.
for row in FREEZE['files']:
    if row['path'].endswith('.py'):
        actual = hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()
        assert actual == row['sha256'], 'Frozen source drift: '+row['path']

source = LOCAL/'frozen/research/model_c040_r1/local/c040_common.py'
tree = ast.parse(source.read_text())
priority_gate = ast.parse('''
assert os.getpriority(os.PRIO_PROCESS, 0) == 15, 'Numerical tasks require actual nice=15; do not add nice twice'
deadline_path = LOCAL/'task_deadline.json'
if deadline_path.is_file() and __import__('time').time() >= json.loads(deadline_path.read_text())['deadline_unix']:
    print('STOP task time budget reached; no new numerical work', flush=True)
    raise SystemExit(78)
priority_path = LOCAL/'short-verification-priority.json'
if priority_path.is_file():
    policy = json.loads(priority_path.read_text())
    alive = True
    try:
        os.kill(policy['owner_pid'], 0)
    except ProcessLookupError:
        alive = False
    if alive and __import__('time').time() < policy['expires_unix'] and Path(sys.argv[0]).name not in policy['allow_scripts']:
        print('DEFER short verification priority', flush=True)
        raise SystemExit(75)
''').body
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name=='admission':
        node.body[1:1] = priority_gate
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        key = node.targets[0].id
        if key in ('ROOT','LOCAL','HERE'):
            node.value = ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),
                args=[ast.Constant(str(dict(ROOT=ROOT,LOCAL=LOCAL,HERE=HERE)[key]))],keywords=[])
adapter = types.ModuleType('film_r2_native')
adapter.__file__ = str(source)
sys.modules[adapter.__name__] = adapter
exec(compile(ast.fix_missing_locations(tree),str(source),'exec'),adapter.__dict__)
globals().update({key:value for key,value in adapter.__dict__.items() if not key.startswith('__')})
sys.modules['common'] = _owner_module


def frozen(path):
    return LOCAL/'frozen'/path


def load_fit():
    source = frozen('research/model_c040_r1/local/fit.py')
    tree = ast.parse(source.read_text())
    tree.body = [n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='c040_common')]
    scope = types.ModuleType('film_r2_fit')
    scope.__file__ = str(source)
    scope.__dict__.update(adapter.__dict__)
    exec(compile(tree,str(source),'exec'),scope.__dict__)
    return scope


def load_assess():
    source = frozen('research/model_c040_r1/local/assess.py')
    tree = ast.parse(source.read_text())
    tree.body = [n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='c040_common')]
    scope = types.ModuleType('film_r2_assess')
    scope.__file__ = str(source)
    scope.__dict__.update(adapter.__dict__)
    exec(compile(tree,str(source),'exec'),scope.__dict__)
    return scope
