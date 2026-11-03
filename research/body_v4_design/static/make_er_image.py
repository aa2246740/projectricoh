#!/usr/bin/python3 -I -B
"""Make an evaluation-only MAIN image: official ilaunch3 with the image-arena
size word 0x200C0DD4 lowered by the extension-region size, checksum at 0x16C
recomputed (same algorithm as research/body_v39/tests/recovery_path.py).
Nothing else changes.  The output must be under the v4-design Scratch dir.

  make_er_image.py <er_bytes_hex> <output ilaunch3>
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
OFFICIAL_SHA = 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-design')
LOAD, HEADER, SIZE_WORD, OLD = 0x2004B000, 0x200, 0x200C0DD4, 0x076C0000


def checksum(data):
    content = data[HEADER:]
    total = sum(byte * (i % 6 + 2) for i, byte in enumerate(content)) & 0xffffffff
    assert total == sum(sum(content[k::6]) * (k + 2) for k in range(6)) & 0xffffffff
    return total


def file_offset(raw, vma):
    for i in range(16):
        source, base, size, _, _ = struct.unpack_from('>5I', raw, 0x20 + 20 * i)
        if base <= vma and vma + 4 <= base + size:
            return source + HEADER + vma - base
    raise AssertionError(('not file-backed', hex(vma)))


def main():
    er, out = int(sys.argv[1], 16), Path(sys.argv[2]).resolve()
    assert out.is_relative_to(SCRATCH)
    assert er % 0x40000 == 0 and 0 < er <= 0x01000000, 'keep 256 KiB alignment of the arena end'
    raw = bytearray(OFFICIAL.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == OFFICIAL_SHA
    assert struct.unpack_from('>I', raw, 0x16C)[0] == checksum(raw), 'official checksum layout'
    off = file_offset(raw, SIZE_WORD)
    assert struct.unpack_from('>I', raw, off)[0] == OLD
    struct.pack_into('>I', raw, off, OLD - er)
    struct.pack_into('>I', raw, 0x16C, checksum(raw))
    out.write_bytes(raw)
    official = OFFICIAL.read_bytes()
    changed = [i for i in range(len(raw)) if raw[i] != official[i]]
    print(json.dumps(dict(output=str(out), sha256=hashlib.sha256(raw).hexdigest(), size_word_file_offset=hex(off),
                          new_size=hex(OLD - er), er_bytes=hex(er), changed_offsets=[hex(i) for i in changed])))


if __name__ == '__main__':
    main()
