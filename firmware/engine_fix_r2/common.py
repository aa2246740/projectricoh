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
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_fix_r2')
    assert not HERE.is_symlink() and not LOCAL.is_symlink() and os.access(HERE, os.W_OK)
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', 'firmware/engine_fix_r2/local/check'], cwd=ROOT, text=True)
    assert 'engine_fix_r2/.gitignore:1:/local/' in ignored
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


def snapshot():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = {ROOT / p for p in tracked if p}
    for relative in ('firmware/resident_v32', 'firmware/v32_load_diag',
                     'research/mount_calib_r1', 'artifacts/firmware/gxr-1.51',
                     'firmware/image_v3', 'research/huzi_luts/local/best_candidates',
                     'research/refit_50mm_r7/local/v6'):
        paths.update((ROOT / relative).rglob('*'))
    paths.update((GCC, LD, OBJDUMP))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)
            if p.is_file() and not p.is_symlink() and HERE not in p.parents}


if __name__ == '__main__':
    import shutil
    guard()
    target = LOCAL / 'scope-before.json'
    if not target.exists():
        save(target, dict(files=snapshot(), git=run(['git', 'status', '--porcelain=v1', '--untracked-files=no'], 'git-before').stdout))
    for relative in ('engine_services', 'containers/product'):
        destination = HERE / relative
        assert not destination.exists(), 'initial copy must never overwrite work'
        shutil.copytree(UPSTREAM / relative, destination, ignore=shutil.ignore_patterns('__pycache__', 'local'))
    print('PASS volume/ignore; frozen scope saved; copied engine_services and containers/product')
