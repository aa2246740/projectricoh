"""Confine full-r4 output; upstream modules and fixtures are read-only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PRODUCT = ROOT / 'firmware/engine_fix_r2/containers/product'
BASE = ROOT / 'firmware/engine_fix_r2/local/product/candidates/full-r3'
OUT = LOCAL / 'full-r4'
RESIDENT = ROOT / 'firmware/resident_v32/resident'
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path = Path(path)
    path.resolve().relative_to(LOCAL.resolve())
    assert not LOCAL.is_symlink() and not path.is_symlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    assert path.read_bytes() == data


def save(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())


def guard():
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/full_r4')
    assert not HERE.is_symlink()
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace' and info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == UUID and info['WritableVolume'] and info['WritableMedia']
    assert os.access('/Volumes/Workspace', os.W_OK)
    disk = subprocess.check_output(['/bin/df', '-h', '/Volumes/Workspace'], text=True)
    ignored = subprocess.check_output(['git', 'check-ignore', '-v', 'firmware/full_r4/local/check'], cwd=ROOT, text=True)
    assert 'firmware/full_r4/.gitignore:1:/local/' in ignored
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    save(LOCAL / 'preflight.json', dict(volume={k: info[k] for k in (
        'MountPoint', 'FilesystemType', 'VolumeUUID', 'WritableVolume', 'WritableMedia')}, df=disk, ignore=ignored))


def run(args, label, timeout=120):
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C', PYTHONDONTWRITEBYTECODE='1',
               CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    write(LOCAL / 'logs' / (label + '.log'), (result.stdout + result.stderr).encode())
    with (LOCAL / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=[str(a) for a in args], returncode=result.returncode)) + '\n')
    assert result.returncode == 0, label + ': ' + result.stdout[-1000:] + result.stderr[-3000:]
    return result


def upstream():
    sys.path.insert(0, str(PRODUCT))
    candidates = load(PRODUCT / 'candidates.py', 'full_r4_candidates')
    return candidates, candidates.pack, candidates.build


def snapshot():
    paths = set()
    for tree in ('firmware/engine_fix_r2/containers', 'firmware/engine_fix_r2/engine_services',
                 'firmware/resident_v32/resident', 'research/huzi_luts/local/best_candidates',
                 'research/mount_calib_r1/local/entries'):
        paths.update(p for p in (ROOT / tree).rglob('*') if p.is_file())
    paths.update(p for p in BASE.rglob('*') if p.is_file())
    paths.update(ROOT / p for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p)
    paths.update((ROOT / p) for p in (
        'firmware/resident_v32/local/resident/trust.c',
        'firmware/resident_v32/local/resident/build/resident.elf',
        'firmware/engine_fix_r2/local/resident/engine-services/libgxr_services.a',
        'firmware/engine_fix_r2/local/product/entries.h',
        'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3',
        'research/gr4_dense_returns_r1/local/candidate/DEEPTBL_50mm_gr4_positive_r1.DAT',
        'research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT',
        'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL',
        'research/gr4_dense_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_positive_r1.DAT',
        'research/mount_calib_r1/local/DEEPTBL_mount_calibrated.DAT'))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths) if HERE not in p.parents}
