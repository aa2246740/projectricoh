"""核对当前解释器和锁定依赖，不安装或更新环境。"""

import importlib.metadata
import json
from pathlib import Path
import os
import sys
import tomllib

from review_support import OUT, REPO

lock = tomllib.loads((REPO / "uv.lock").read_text())
checks = []
for package in lock["package"]:
    if "version" not in package:
        continue
    try:
        actual = importlib.metadata.version(package["name"])
    except importlib.metadata.PackageNotFoundError:
        checks.append({"name": package["name"], "installed": False, "locked": package["version"]})
        continue
    checks.append({"name": package["name"], "locked": package["version"], "actual": actual,
                   "same": actual == package["version"]})
result = {"python": sys.version, "nice": os.getpriority(os.PRIO_PROCESS, 0),
          "packages": checks, "mismatches": [row for row in checks if row.get("same") is False]}
(OUT / "environment-versions.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: value for key, value in result.items() if key != "packages"}))
assert not result["mismatches"] and result["nice"] == 10
