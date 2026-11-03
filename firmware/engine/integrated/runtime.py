"""Task-scoped I/O, reproducible commands, and volume guard."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'
SRC = HERE / 'src'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def guard():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info.get('MountPoint') == '/Volumes/Workspace'
    assert info.get('FilesystemType') == 'apfs'
    assert info.get('VolumeUUID') == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info.get('WritableVolume') and info.get('WritableMedia') and os.access(HERE, os.W_OK)
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', str(HERE.relative_to(ROOT) / 'local/probe')], cwd=ROOT, text=True)
    assert 'integrated/.gitignore:1:/local/' in ignored
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    (LOCAL / 'preflight.json').write_text(json.dumps({'volume': {k: info.get(k) for k in ('VolumeUUID', 'MountPoint', 'FilesystemType', 'WritableVolume', 'WritableMedia')}, 'ignore': ignored}, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def run(args, label, *, check=True, env=None):
    full_env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1')
    if env:
        full_env.update(env)
    proc = subprocess.run([str(a) for a in args], cwd=ROOT, env=full_env, capture_output=True, text=True)
    logs = LOCAL / 'logs'
    logs.mkdir(exist_ok=True)
    output = proc.stdout + proc.stderr
    (logs / (label + '.log')).write_text(output)
    if proc.returncode:
        failures = LOCAL / 'failures'
        failures.mkdir(exist_ok=True)
        (failures / (label + '-' + hashlib.sha256(output.encode()).hexdigest()[:12] + '.log')).write_text(output)
    with (LOCAL / 'commands.jsonl').open('a') as f:
        f.write(json.dumps({'label': label, 'argv': [str(a) for a in args], 'returncode': proc.returncode}) + '\n')
    if check and proc.returncode:
        raise RuntimeError(label + ': ' + output[-2800:])
    return proc
