"""Task-local guards, ELF reader and captured commands. Run with python3 -I -B."""
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
R = ROOT / 'firmware/resident_v32/resident'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
RESIDENT = ROOT / 'firmware/resident_v32/local/resident/build/resident.elf'
FULL = ROOT / 'firmware/resident_v32/local/product/candidates/full/GXRCE.DAT'
APPROVED = ROOT / 'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.resolve().relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def guard():
    info = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['MountPoint'] == '/Volumes/Workspace'
    assert info['FilesystemType'] == 'apfs'
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/v32_load_diag')
    assert not HERE.is_symlink() and not LOCAL.is_symlink()
    ignore = subprocess.check_output(['git', 'check-ignore', '-v',
                                     'firmware/v32_load_diag/local/check'], cwd=ROOT, text=True)
    assert 'firmware/v32_load_diag/.gitignore:1:/local/' in ignore
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    save(LOCAL / 'preflight.json', dict(volume={k: info[k] for k in (
        'MountPoint', 'FilesystemType', 'VolumeUUID', 'WritableVolume', 'WritableMedia')}, ignore=ignore))


def run(args, label, *, check=True, timeout=120):
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    log = LOCAL / 'logs' / (label + '.log')
    log.parent.mkdir(exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    with (LOCAL / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(label=label, argv=[str(a) for a in args],
                                     returncode=result.returncode)) + '\n')
    if result.returncode:
        failures = LOCAL / 'failures'
        failures.mkdir(exist_ok=True)
        (failures / (label + '-' + hashlib.sha256(log.read_bytes()).hexdigest()[:12] + '.log')).write_bytes(log.read_bytes())
        if check:
            raise RuntimeError(f'{label}: exit {result.returncode}: {log.read_text()[-2200:]}')
    return result


Elf = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'diag_elf_reader').Elf
