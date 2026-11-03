#!/usr/bin/python3
"""Bind the qualification counterexample to the exact published DAT bytes."""
import hashlib
import json
import os
from pathlib import Path
import pickle
import struct
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    target = HERE / 'evidence/qualification-binding.json'
    assert not target.exists()
    source = ROOT / 'research/v310_body/fix/local/valid-mount-look-r5-gate-input.z'
    state = pickle.loads(zlib.decompress(source.read_bytes()))
    def mem(at, n):
        for base, data, _ in state['regions']:
            if base <= at and at + n <= base + len(data):
                return data[at - base:at - base + n]
        raise ValueError(hex(at))
    dat = (ROOT / 'firmware/package_v310_g155b_test/GXRCE.DAT').read_bytes()
    base = int.from_bytes(mem(0x20054770, 4), 'big') - int.from_bytes(dat[132:136], 'big')
    off = int.from_bytes(dat[144:148], 'big')
    length = int.from_bytes(dat[148:152], 'big')
    relocated = bytearray(dat)
    for at in range(off, off + length, 8):
        patch, relative = struct.unpack_from('>II', dat, at)
        struct.pack_into('>I', relocated, patch, base + relative)
    actual = bytes(mem(base, len(dat)))
    assert actual == relocated
    result = dict(status='PASS', source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        DAT_sha256=hashlib.sha256(dat).hexdigest(), DAT_bytes=len(dat),
        loaded_base=hex(base), relocation_count=length // 8,
        entire_loaded_DAT_equal=True, compared_bytes=len(actual),
        qualification_entry=hex(state['expected_function']))
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
