"""Recheck all frozen inputs without refreshing any expected digest."""
import hashlib
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
before = json.loads((HERE / "protected-before.json").read_text())
changed, missing = [], []
for name, digest in before.items():
    p = ROOT / name
    if not p.is_file(): missing.append(name)
    elif hashlib.sha256(p.read_bytes()).hexdigest() != digest: changed.append(name)
now = set()
for rel in ("firmware/resident_v35", "firmware/image_v35", "firmware/resident_v36",
            "firmware/image_v36", "tools/native_harness", "research/review_v35_body",
            "firmware/engine_v37", "artifacts/firmware/gxr-1.51"):
    now.update(str(p.relative_to(ROOT)) for p in (ROOT / rel).rglob("*") if p.is_file())
now.add("artifacts/downloads/gxr-151.zip")
added = sorted(now - before.keys())
result = dict(files=len(before), changed=changed, missing=missing, added=added,
              unchanged=not (changed or missing or added))
(HERE / "protected-after.json").write_text(json.dumps(result, indent=2)+"\n")
assert result["unchanged"], result
print("PASS", len(before), "frozen files unchanged; no files added to protected trees")
