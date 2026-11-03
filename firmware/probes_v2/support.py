"""Task-scoped storage, subprocess evidence and ELF32 inspection."""
import hashlib
import os
from pathlib import Path
import plistlib
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
VOLUME = Path('/Volumes/Workspace')
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight():
    p = subprocess.run(['/usr/sbin/diskutil', 'info', '-plist', str(VOLUME)],
                       capture_output=True, check=True, timeout=10)
    info = plistlib.loads(p.stdout)
    required = (info.get('MountPoint') == str(VOLUME),
                info.get('VolumeUUID') == UUID,
                info.get('FilesystemType') == 'apfs',
                info.get('WritableVolume') is True,
                os.access(VOLUME, os.W_OK))
    if not all(required):
        raise RuntimeError('Workspace volume identity, APFS or writable check failed')
    if HERE != Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/probes_v2'):
        raise RuntimeError('unexpected checkout; refusing writes')
    if LOCAL.is_symlink():
        raise RuntimeError('local/ must not be a symlink')
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    if (LOCAL / 'tmp').is_symlink():
        raise RuntimeError('local/tmp must not be a symlink')
    return {k: info[k] for k in ('MountPoint', 'VolumeUUID', 'FilesystemType', 'WritableVolume')}


def run(argv, log, timeout=30, check=True):
    log = Path(log)
    if not log.resolve().is_relative_to(LOCAL):
        raise RuntimeError('logs must remain in task local/')
    env = dict(os.environ, TMPDIR=str(LOCAL / 'tmp'), LC_ALL='C',
               PYTHONDONTWRITEBYTECODE='1', CLANG_MODULE_CACHE_PATH=str(LOCAL / 'tmp/modules'))
    p = subprocess.run([str(a) for a in argv], cwd=ROOT, env=env, text=True,
                       capture_output=True, timeout=timeout)
    log.write_text(p.stdout + p.stderr)
    if p.returncode:
        failures = LOCAL / 'failures'
        failures.mkdir(exist_ok=True)
        raw = (p.stdout+p.stderr).encode()
        (failures / (log.stem+'-'+hashlib.sha256(raw).hexdigest()[:12]+'.log')).write_bytes(raw)
    if check and p.returncode:
        raise RuntimeError(f'{log.name}: exit {p.returncode}; see {log}')
    return p


class Elf:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        if self.data[:6] != b'\x7fELF\x01\x02':
            raise ValueError('expected big-endian ELF32')
        h = struct.unpack_from('>HHIIIIIHHHHHH', self.data, 16)
        if h[1] != 88 or h[10] != 40:
            raise ValueError('expected M32R and 40-byte section headers')
        self.entry = h[3]
        raw = [struct.unpack_from('>10I', self.data, h[5] + 40*i) for i in range(h[11])]
        names = self.data[raw[h[12]][4]:raw[h[12]][4]+raw[h[12]][5]]
        self.sections = []
        for i, s in enumerate(raw):
            self.sections.append(dict(index=i, name=self.string(names, s[0]), type=s[1],
                                      flags=s[2], va=s[3], offset=s[4], size=s[5],
                                      link=s[6], info=s[7], align=s[8], entsize=s[9]))
        self.symbols = {}
        for s in self.sections:
            if s['type'] != 2:
                continue
            strings = self.content(self.sections[s['link']])
            for off in range(0, s['size'], 16):
                n, value, size, info, other, section = struct.unpack_from('>IIIBBH', self.data, s['offset']+off)
                name = self.string(strings, n)
                if name:
                    self.symbols[name] = dict(value=value, size=size, section=section, info=info, other=other)

    @staticmethod
    def string(data, offset):
        return data[offset:data.index(0, offset)].decode('ascii')

    def content(self, section):
        return self.data[section['offset']:section['offset']+section['size']]

    def section(self, name):
        return next(s for s in self.sections if s['name'] == name)
