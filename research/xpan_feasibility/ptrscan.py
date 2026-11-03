#!/usr/bin/python3 -I -B
"""Read-only: find big-endian 32-bit words in a firmware file equal to given VMAs
(or inside a VMA range) and print their file offsets and VMAs."""
import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)

name = sys.argv[1]
targets = [int(x, 0) for x in sys.argv[2:]]
data = (hp.FIRM / name).read_bytes()
secs = hp.sections(data)
for s, v, n in secs:
    for o in range(s, s + n - 3, 1):
        w = struct.unpack_from('>I', data, o)[0]
        if w in targets:
            print(f'file {o:#x} vma {v + o - s:#x} = {w:#x}')
