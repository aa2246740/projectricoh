"""从最终 pytest、覆盖率与文件摘要生成检查回执。"""

from __future__ import annotations

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1")


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    run = read(HERE / "make-check-final.json")
    assert run["exit_code"] == 0 and not run["timeout"]
    xml_path = SCRATCH / "check-final.xml"
    cases = list(ET.parse(xml_path).getroot().iter("testcase"))
    failed = [case for case in cases if case.find("failure") is not None or case.find("error") is not None]
    skipped = [case for case in cases if case.find("skipped") is not None]
    assert not failed and not skipped
    own = [case for case in cases if case.get("classname", "").split(".")[-1] == "test_g152"]
    defaults = [case for case in own if case.get("name", "").startswith("test_every_look_default_has_the_camera_552_bytes[")]
    points = [case for case in own if case.get("name", "").startswith("test_every_look_control_point_has_the_camera_552_bytes[")]
    assert len(defaults) == 120 and len(points) == 60
    catalog = read(SCRATCH / "ui_catalog.json")
    point_comparisons = 2 * sum(len(c["levels"]) for unit in catalog["units"] for look in unit["looks"] for c in look["controls"])
    coverage = read(SCRATCH / "coverage-final.json")
    before, after = read(HERE / "source-final-before.json"), read(HERE / "source-final-after.json")
    assert before == after
    assert after["branch"] == "main" and after["head"] == "e73a7af474e137b26862f252da0a8ad58b5d3793"
    shutil.copyfile(xml_path, HERE / "pytest.xml")
    summary = {"status": "PASS", "tests": len(cases), "passed": len(cases), "failed": 0, "errors": 0,
               "skipped": 0, "forced_reruns": 0, "new_generation_tests": len(own),
               "default_552_comparisons": len(defaults), "single_control_552_comparisons": point_comparisons,
               "coverage": coverage["totals"], "coverage_source_sha256": digest(SCRATCH / "coverage-final.json"),
               "pytest_sha256": digest(xml_path), "source_files": len(after["source"]),
               "source_tree_sha256": hashlib.sha256(json.dumps(after["source"], sort_keys=True).encode()).hexdigest(),
               "source_unchanged": True, "git_metadata_unchanged": True, "head": after["head"],
               "byte_proof_sha256": digest(HERE / "byte_equality.json"), "ui_proof_sha256": digest(HERE / "ui.json")}
    (HERE / "checks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    coverage_summary = {"meta": coverage["meta"], "totals": coverage["totals"],
                        "files": {name: value["summary"] for name, value in coverage["files"].items()}}
    (HERE / "coverage.json").write_text(json.dumps(coverage_summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
