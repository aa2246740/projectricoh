#!/usr/bin/env python3
"""Re-execute an archived local model under a fresh evidence name."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT/'tools/gxr_emulator'
OUT = HERE/'local'


def main():
    reference, name = sys.argv[1:]
    if any(Path(value).name != value for value in (reference, name)):
        raise ValueError('simple evidence names required')
    if (OUT/(name+'.json')).exists():
        raise ValueError('evidence already exists')
    result = json.loads((OUT/(reference+'.json')).read_text())
    archive = OUT/(reference+'-sources')
    for module, expected in result['source_hashes'].items():
        actual = hashlib.sha256((archive/module).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('archived source changed: '+module)
    library = TOOLS/'build/libgxr_m32r.dylib'
    if hashlib.sha256(library.read_bytes()).hexdigest() != result['library_sha256']:
        raise ValueError('frozen GNU library changed')
    sys.path.insert(0, str(archive))
    for module in ('image', 'backend', 'boot', 'legacy', 'unit_peer', 'm2'):
        loaded = importlib.import_module(module)
        if hasattr(loaded, 'ROOT'):
            loaded.ROOT = ROOT
        if hasattr(loaded, 'HERE'):
            loaded.HERE = TOOLS
    peer = sys.modules['unit_peer']
    peer.SOURCE = ROOT/'tools/native_harness/product_execute.py'
    peer.UNIT = ROOT/'artifacts/firmware/gxr-1.51/jlaunch3'
    runner = sys.modules['m2']
    runner.OUT = OUT
    runner.SOURCE_HASHES = result['source_hashes']
    arguments = {**result['arguments'], 'name': name, 'output_dir': str(OUT)}
    runner.run(SimpleNamespace(**arguments))


if __name__ == '__main__':
    main()
