"""Local, offline helpers. No camera I/O or firmware writes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PIPE = ROOT / 'research/gr_complete_pipeline'


def safe_path(value):
    p = Path(value).expanduser()
    if 'Volumes' in p.parts:
        raise ValueError('Mounted-volume paths are prohibited for this research task')
    p = p.resolve()
    if 'Volumes' in p.parts:
        raise ValueError('Symlink resolves to a prohibited mounted-volume path')
    return p


def output_path(value):
    p = safe_path(value)
    if not p.is_relative_to(HERE):
        raise ValueError('Output must remain inside research/canonical_gr_pack')
    return p


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(safe_path(path).read_text())


def save(path, obj):
    p = output_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, safe_path(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def record(values, fmt, endian='>'):
    values = [int(x) for x in values]
    raw = struct.pack(endian + fmt * len(values), *values)
    return dict(values=values, hex=raw.hex(), bytes=len(raw), sha256=sha(raw))


class M32RImage:
    def __init__(self, path):
        self.path = safe_path(path)
        self.data = self.path.read_bytes()
        self.sections = [struct.unpack_from('>5I', self.data, 32 + i * 20) for i in range(16)]

    def off(self, address, size=1):
        for source, vma, length, _, _ in self.sections:
            if vma <= address and address + size <= vma + length:
                return source + 512 + address - vma
        raise ValueError(f'Address range not in initialized image: {address:#x}+{size}')

    def at(self, address, size):
        offset = self.off(address, size)
        return self.data[offset:offset + size]

    def block(self, address, count, fmt):
        raw = self.at(address, count * struct.calcsize(fmt))
        return {**record(struct.unpack('>' + fmt * count, raw), fmt),
                'source_path': str(self.path), 'source_vma': hex(address),
                'source_file_offset': hex(self.off(address, len(raw))),
                'evidence_level': 'STATIC_BYTES'}
