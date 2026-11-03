#!/usr/bin/python3 -I -B
"""Read-only: hex dump of a VMA range from a firmware image (stdout only)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)
name, vma, n = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
data = (hp.FIRM / name).read_bytes()
off = hp.mapped(hp.sections(data), vma, reverse=True)
print(f'{name} vma {vma:#x} -> file {off:#x}' if off is not None else 'unmapped')
for i in range(0, n, 16):
    chunk = data[off + i:off + i + min(16, n - i)]
    print(f'{vma + i:08x}: ' + chunk.hex(' ') + '  ' + ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk))
