#!/usr/bin/python3 -I -B
"""Read-only: map file offsets to VMAs and list linear constant-propagation
references to a VMA range in the ilaunch3 / jlaunch3 disassembly (candidates,
not interprocedural proofs). Output to stdout only."""
import importlib.util
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('hp', ROOT / 'research/hidden_processing/analyze.py')
hp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hp)

def vma_of(name, off):
    data = (hp.FIRM / name).read_bytes()
    return hp.mapped(hp.sections(data), off)

def main():
    name = sys.argv[1]
    cmd = sys.argv[2]
    if cmd == 'vma':
        for a in sys.argv[3:]:
            v = vma_of(name, int(a, 0))
            print(a, hex(v) if v else None)
    elif cmd == 'refs':
        lo, hi = int(sys.argv[3], 0), int(sys.argv[4], 0)
        for va, tgt, kind, path, no, op in hp.refs(name):
            if lo <= tgt < hi:
                print(f'{va:08x} {tgt:08x} {kind} {path}:{no} {op}')

main()
