"""核对修复轮测试、覆盖率和源码稳定性，保存最终回执。"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def main() -> None:
    run = read("fix-make-check.json")
    assert run["exit_code"] == 0 and not run["timeout"]
    cases = list(ET.parse(HERE / "fix-pytest.xml").getroot().iter("testcase"))
    assert all(case.find(key) is None for case in cases for key in ("failure", "error", "skipped"))
    cache = [case for case in cases if case.get("name", "").startswith("test_recipe_cache_after_data_change[")]
    copy = [case for case in cases if case.get("name", "").startswith("test_unsupported_generation_copy_keeps_numbers_in_detail[")]
    assert len(cache) == 5 and len(copy) == 5
    before, after = read("source-fix-check-before.json"), read("source-fix-check-after.json")
    start = read("source-fix-start-before.json")
    assert before == after and start["git_metadata"] == after["git_metadata"]
    assert start["source"]["src/gxr_studio/engine/data/final.json"] == after["source"]["src/gxr_studio/engine/data/final.json"]
    coverage = read("fix-coverage-full.json")
    summary = {
        "status": "PASS", "full_check_runs": 1, "passed": len(cases), "failed": 0, "errors": 0, "skipped": 0, "reruns": 0,
        "cache_cases": len(cache), "copy_cases": len(copy), "coverage": coverage["totals"],
        "source_files": len(after["source"]), "source_unchanged_during_check": True, "git_metadata_unchanged": True,
        "head": after["head"], "branch": after["branch"],
        "source_tree_sha256": hashlib.sha256(json.dumps(after["source"], sort_keys=True).encode()).hexdigest(),
        "engine_table_sha256": after["source"]["src/gxr_studio/engine/data/final.json"],
        "scenarios": read("fix-scenarios.json")["scenarios"],
    }
    (HERE / "fix-checks.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
