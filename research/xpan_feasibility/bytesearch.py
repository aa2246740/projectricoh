#!/usr/bin/python3 -I -B
"""Read-only: search a firmware file for a hex byte pattern; print file offset, VMA, context."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)
name, pat = sys.argv[1], bytes.fromhex(sys.argv[2])
ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 16
data = (hp.FIRM / name).read_bytes()
secs = hp.sections(data)
i = data.find(pat)
while i >= 0:
    v = hp.mapped(secs, i)
    print(f'file {i:#x} vma {v:#x}' if v else f'file {i:#x} vma ?', data[max(0, i - ctx):i + len(pat) + ctx].hex(' '))
    i = data.find(pat, i + 1)
