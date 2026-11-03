"""复审独立输出与临时目录，复用机器码驱动，不改实现方文件。"""
from pathlib import Path
import hashlib
import importlib.util
import os
import sys
import types

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-r1')
TMP.mkdir(parents=True, exist_ok=True)
(OUT / 'evidence').mkdir(exist_ok=True)
os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
sys.dont_write_bytecode = True
os.environ.setdefault('GXR_HARNESS_BACKEND', 'c')
ADAPTATIONS = []


def adapted(name, relative, changes=()):
    path = ROOT / relative
    source = path.read_text()
    original = source
    for old, new in changes:
        assert source.count(old) == 1, (relative, old)
        source = source.replace(old, new)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), vars(module))
    ADAPTATIONS.append(dict(path=relative, source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                            executed_sha256=hashlib.sha256(source.encode()).hexdigest(), changes=list(changes)))
    return module


N = adapted('native_support', 'research/g154/native_support.py', [
    ("TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-impl-r1')", f'TMP=Path({str(TMP)!r})')])
REF = adapted('reference', 'research/g154/reference.py', [
    ("TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-impl-r1/reference')", f'TMP=Path({str(TMP / "reference")!r})'),
    ('module.HERE=HERE', f'module.HERE=Path({str(OUT)!r})')])
V = adapted('verify', 'research/g154/verify.py')
V.HERE = OUT
CC = adapted('cache_checks', 'research/g154/cache_checks.py')
CC.HERE = OUT
SC = adapted('scenes', 'research/g154/scenes.py')
ST = adapted('state_checks', 'research/g154/state_checks.py', [
    ("module.OUT=HERE/('local/cross-control' if CONTROL else 'local/cross')",
     f"module.OUT=Path({str(TMP / 'cross-control')!r} if CONTROL else {str(TMP / 'cross')!r})")])
ST.HERE = OUT
CAP = adapted('cap_checks', 'research/g154/cap_checks.py')
CAP.HERE = OUT
H, Camera = N.H, N.Camera


def save(name, value):
    import json
    (OUT / 'evidence' / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()
