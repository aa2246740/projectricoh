"""核对本轮实际构建包、成员摘要和源码一致性。"""

import importlib.util
import json
from pathlib import Path
import tarfile
import zipfile

from review_support import OUT, REPO, TEMP, digest

spec = importlib.util.spec_from_file_location("review_package_check", REPO / "scripts/private_bytes.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
source = json.loads((OUT / "source-before.json").read_text())
hits = []
artifacts = []
matches = []

for path in sorted((TEMP / "dist").iterdir()):
    if path.suffix not in (".whl", ".gz"):
        continue
    members = []
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            entries = [(entry.filename, archive.read(entry)) for entry in archive.infolist() if not entry.is_dir()]
    else:
        with tarfile.open(path) as archive:
            entries = [(entry.name, archive.extractfile(entry).read()) for entry in archive if entry.isfile()]
    for name, data in entries:
        found = checker.scan_bytes(path.name + "!" + name, data)
        hits.extend(found)
        members.append({"name": name, "size": len(data), "sha256": digest(data), "hits": found})
        if path.suffix == ".whl" and ("src/" + name) in source:
            matches.append({"source": "studio/src/" + name, "same": digest(data) == source["src/" + name]})
    artifacts.append({"name": path.name, "size": path.stat().st_size, "sha256": digest(path.read_bytes()),
                      "member_count": len(members), "members": members})

assert len(artifacts) == 2
assert len(matches) > 80 and all(row["same"] for row in matches)
result = {"artifacts": artifacts, "wheel_source_matches": matches, "hits": hits,
          "repository_file_count": len(source)}
(OUT / "package-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"artifacts": [{key: value for key, value in artifact.items() if key != "members"} for artifact in artifacts],
                  "wheel_source_matches": len(matches), "hits": hits}, ensure_ascii=False))
raise SystemExit(bool(hits))
