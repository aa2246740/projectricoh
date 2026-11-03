"""Offline build helpers. All generated files stay below this task."""
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
R = ROOT / 'firmware/resident_v34c/resident'
GEN114 = ROOT / 'firmware/engine_v35_publish'
SERVICE_COPY = LOCAL / 'services114'
S = SERVICE_COPY / 'candidate/engine_services'
PRODUCT = ROOT / 'firmware/resident_v34c/acceptance/containers/product'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
ARCHIVE = SERVICE_COPY / 'build/libgxr_services.a'
ARCHIVE114 = GEN114 / 'candidate/local/resident/engine-services/libgxr_services.a'
BODY = ROOT / 'firmware/image_v34c/local/body-final-v34c/candidate/SD_ROOT/ilaunch3'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
RESIDENT = R.parent / 'local/resident/build/resident.elf'
FULL = R.parent / 'acceptance/local/full-r11/GXRCE.DAT'
FULL114 = GEN114 / 'local/staged/SD_ROOT/GXRCE.DAT'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    p = Path(p)
    p.resolve().relative_to(HERE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def guard():
    v = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert v['FilesystemType'] == 'apfs' and v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['MountPoint'] == '/Volumes/Workspace' and v['WritableVolume'] and v['WritableMedia']
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/lut_p0_timing')
    assert not HERE.is_symlink() and not LOCAL.is_symlink()
    assert sha(BODY) == '24b1de0e46ea00adeacd224da28770e185b05a08686c40c647032c533c021f72'
    assert sha(OFFICIAL) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'check')], cwd=ROOT, check=True)


def run(args, label, timeout=120, check=True):
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=timeout)
    p = LOCAL / 'logs' / label
    p.parent.mkdir(parents=True, exist_ok=True)
    p.with_suffix('.stdout').write_text(result.stdout)
    p.with_suffix('.stderr').write_text(result.stderr)
    with (LOCAL / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=[str(a) for a in args], returncode=result.returncode)) + '\n')
    if result.returncode and check:
        failure=LOCAL/'failures'/(label+'-'+hashlib.sha256((result.stdout+result.stderr).encode()).hexdigest()[:12]+'.log')
        failure.parent.mkdir(exist_ok=True);failure.write_text(result.stdout+result.stderr)
        raise RuntimeError(f'{label}: exit={result.returncode}\n' + result.stderr[-2500:] + result.stdout[-1000:])
    return result


Elf = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'p0_elf_reader').Elf


def native(va, n):
    data = OFFICIAL.read_bytes()
    import struct
    for i in range(16):
        src, base, size, _, _ = struct.unpack_from('>5I', data, 32 + 20*i)
        if base <= va and va+n <= base+size:
            return data[512+src+va-base:512+src+va-base+n]
    raise AssertionError(hex(va))
