"""保留完整逐行覆盖率，省去非必要的函数级明细。"""

import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
path = OUT / "coverage.json"
original = path.read_bytes()
data = json.loads(original)
totals = dict(data["totals"])
line_tables = {name: {key: value for key, value in item.items() if key != "functions"}
               for name, item in data["files"].items()}
removed = sum(len(item.pop("functions", {})) for item in data["files"].values())
assert data["totals"] == totals and data["files"] == line_tables
path.write_text(json.dumps(data, ensure_ascii=False) + "\n")
receipt = {"original_export_sha256": hashlib.sha256(original).hexdigest(),
           "line_export_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
           "removed_function_blocks": removed, "line_tables_identical": True, "totals_identical": True}
(OUT / "coverage_line_export.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
