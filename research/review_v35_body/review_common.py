"""Review-only bindings. All output and decode caches stay in this folder."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools/native_harness"))
import python_backend
python_backend.CACHE = HERE / "decode"

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

def freeze():
    paths = set()
    for name in ("firmware/resident_v35", "firmware/image_v35", "firmware/engine_v37", "tools/native_harness", "artifacts/firmware/gxr-1.51"):
        paths.update(p for p in (ROOT / name).rglob("*") if p.is_file())
    paths.add(ROOT / "artifacts/downloads/gxr-151.zip")
    save("protected-before.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)})

if __name__ == "__main__":
    freeze()
