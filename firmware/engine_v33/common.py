"""Scoped host-only build helpers. Run with /usr/bin/python3 -I -B."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
UPSTREAM = ROOT / 'firmware/resident_v32'
RESIDENT = UPSTREAM / 'resident'
PRODUCT = HERE / 'containers/product'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path = Path(path)
    path.resolve().relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def guard():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v33')
    assert not HERE.is_symlink() and not LOCAL.is_symlink() and os.access(HERE, os.W_OK)
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', 'firmware/engine_v33/local/check'], cwd=ROOT, text=True)
    assert 'engine_v33/.gitignore:1:/local/' in ignored
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    save(LOCAL / 'preflight.json', dict(volume={k: info[k] for k in (
        'MountPoint', 'FilesystemType', 'VolumeUUID', 'WritableVolume', 'WritableMedia')}, ignore=ignored))


def run(args, label, *, check=True, timeout=120, env=None):
    environment = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1',
        CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'), ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', GIT_OPTIONAL_LOCKS='0')
    environment.update(env or {})
    p = subprocess.run([str(a) for a in args], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout)
    logs = LOCAL / 'logs'; logs.mkdir(exist_ok=True)
    output = p.stdout + p.stderr
    (logs / (label + '.log')).write_text(output)
    with (LOCAL / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=[str(a) for a in args], returncode=p.returncode)) + '\n')
    if p.returncode:
        failures = LOCAL / 'failures'; failures.mkdir(exist_ok=True)
        (failures / (label + '-' + hashlib.sha256(output.encode()).hexdigest()[:12] + '.log')).write_text(output)
        if check:
            raise RuntimeError(label + ': ' + output[-2400:])
    return p


R3 = ROOT / 'firmware/engine_fix_r2/local/product/candidates/full-r3'
BASE = ROOT / 'firmware/full_r4/local/full-r4'
R5 = ROOT / 'firmware/full_r5/local/full-r5'
OUT = LOCAL / 'full-r6'

def write(path, data):
    path = Path(path)
    path.resolve().relative_to(LOCAL.resolve())
    assert not LOCAL.is_symlink() and not path.is_symlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    assert path.read_bytes() == data

def snapshot():
    upstream = load(ROOT / 'firmware/full_r5/common.py', 'v33_frozen_sources')
    frozen = upstream.snapshot()
    for tree in ('firmware/engine_fix_r2', 'firmware/full_r5', 'research/review_full_r4'):
        for p in (ROOT / tree).rglob('*'):
            if p.is_file() and p.name != 'decisions.tsv':
                frozen[str(p.relative_to(ROOT))] = sha(p)
    return frozen

def freeze_check():
    path = HERE / 'local/inputs-before.json'
    now = snapshot()
    if not path.exists():
        save(path, now)
    old = json.loads(path.read_text())
    diff = [dict(path=p, before=old.get(p), after=now.get(p))
            for p in sorted(old.keys() | now.keys()) if old.get(p) != now.get(p)]
    if diff:
        save(LOCAL / 'protected-input-failure.json', diff)
        raise RuntimeError('STOP_PROTECTED_INPUT_CHANGED: ' + repr(diff))
    return old
