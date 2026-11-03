"""Read-only review helpers. All generated files must stay under this directory."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
START_UTC = '2026-10-27T09:52:25Z'
DEADLINE_UTC = '2026-10-27T12:52:25Z'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def save(name, data):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

