"""Scoped host research helpers. No camera, firmware writer, or target execution."""
import os
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import importlib.util
import json
import plistlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
sys.path.insert(0, str(HERE))
import freeze


def guard():
    d = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and d['MountPoint'] == '/Volumes/Workspace'
    assert d['FilesystemType'] == 'apfs' and d['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(d[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert not LOCAL.is_symlink()
    subprocess.run(['/bin/df', '-h', '/Volumes/Workspace'], check=True, capture_output=True)
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    freeze.verify()
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    for k in ('TMPDIR', 'TMP', 'TEMP', 'CLANG_MODULE_CACHE_PATH'):
        os.environ[k] = str(LOCAL / 'tmp')
    for k in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[k] = '1'
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'


guard()


def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(ROOT):
            raise PermissionError('Read outside named checkout: ' + str(p))
        if write and not p.is_relative_to(HERE):
            raise PermissionError('Write outside task: ' + str(p))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for value in (args[:2] if event == 'os.rename' else args[:1]):
            if not Path(os.fsdecode(value)).resolve().is_relative_to(HERE):
                raise PermissionError('Mutation outside task: ' + str(value))


sys.addaudithook(audit)


def plain(v):
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if isinstance(v, Path):
        return str(v)
    if hasattr(v, 'tolist'):
        return plain(v.tolist())
    return v


def dump(path, data):
    p = LOCAL / path
    assert p.resolve().is_relative_to(LOCAL)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(data), indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class Image:
    def __init__(self, name):
        import struct
        self.path = ROOT / 'artifacts/firmware/gxr-1.51' / name
        self.data = self.path.read_bytes()
        self.sections = [struct.unpack_from('>5I', self.data, 32+20*i) for i in range(16)]

    def offset(self, va, n):
        hits = [f+512+va-v for f, v, size, _, _ in self.sections if v <= va and va+n <= v+size]
        assert len(hits) == 1, (hex(va), n)
        return hits[0]

    def read(self, va, n):
        offset = self.offset(va, n)
        return self.data[offset:offset+n]

    def va(self, offset):
        hits = [va+offset-f-512 for f, va, size, _, _ in self.sections if f+512 <= offset < f+512+size]
        assert len(hits) == 1
        return hits[0]


def disasm(image, name, start, end):
    folder = LOCAL / 're'
    folder.mkdir(exist_ok=True)
    raw = folder / (name + '.bin')
    raw.write_bytes(image.read(start, end-start))
    argv = [str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '-D', '-b', 'binary',
            '-m', 'm32r', '-EB', '--adjust-vma=' + hex(start), str(raw)]
    cp = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=20)
    (folder / (name + '.asm.txt')).write_text(cp.stdout)
    return {'image': str(image.path.relative_to(ROOT)), 'start': hex(start), 'end': hex(end),
            'offset': image.offset(start, end-start), 'sha256': freeze.digest(raw), 'argv': argv}
