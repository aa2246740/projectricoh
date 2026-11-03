"""从实际回执核对测试计数、覆盖率，以及源码和输入的稳定性。"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = ROOT / "studio"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=STUDIO, env=env).decode().strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=STUDIO, env=env).decode().strip()
    paths = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=STUDIO, env=env).decode().split("\0")
    source = {p: digest(STUDIO / p) for p in sorted(set(paths)) if p and (STUDIO / p).is_file()}
    json_file("source-check-after.json", source)
    git = STUDIO / ".git"
    if git.is_file():
        git = (STUDIO / git.read_text().strip().split(": ", 1)[1]).resolve()
    metadata = {str(p.relative_to(git)): digest(p) for p in sorted(git.rglob("*")) if p.is_file()}
    json_file("git-after.json", metadata)
    inputs = json.loads((HERE / "inputs-before.json").read_text())
    current_inputs = {p: digest(ROOT / p) for p in inputs}
    json_file("inputs-after.json", current_inputs)
    cases = list(ET.parse(HERE / "make-check.xml").iter("testcase"))
    failures = sum(c.find("failure") is not None for c in cases)
    errors = sum(c.find("error") is not None for c in cases)
    skips = sum(c.find("skipped") is not None for c in cases)
    reruns = sum(len(list(c.iter("rerunFailure"))) + len(list(c.iter("flakyFailure"))) for c in cases)
    counts = Counter(c.attrib.get("classname", "") for c in cases)
    coverage = json.loads((HERE / "make-check-coverage.json").read_text())["totals"]
    log = (HERE / "make-check.log").read_text()
    receipt = json.loads((HERE / "make-check.json").read_text())
    equality = json.loads((HERE / "byte-equality.json").read_text())
    legacy = json.loads((HERE / "old-generations.json").read_text())
    result = {"tests": len(cases), "passed": len(cases) - failures - errors - skips, "failures": failures, "errors": errors,
              "skipped": skips, "reruns": reruns, "test_counts_by_module": dict(counts),
              "coverage_percent": coverage["percent_covered"], "coverage_statements": coverage["num_statements"],
              "covered_statements": coverage["covered_lines"], "source_files": len(source), "git_files": len(metadata),
              "input_files": len(inputs), "source_unchanged_during_check": source == json.loads((HERE / "source-check-before.json").read_text()),
              "git_unchanged": metadata == json.loads((HERE / "git-before.json").read_text()), "inputs_unchanged": inputs == current_inputs,
              "head": head, "branch": branch, "make_check_exit_code": receipt["exit_code"],
              "private_bytes_check": next(line for line in log.splitlines() if line.startswith("private bytes: checked")),
              "engine_final_sha256": digest(STUDIO / "src/gxr_studio/engine/data/final.json"),
              "full_row_default_comparisons": equality["default_comparisons"], "single_control_comparisons": equality["single_control_comparisons"],
              "legacy_comparisons": legacy["comparisons"]}
    result["status"] = "PASS" if (
        not (failures or errors or skips or reruns or receipt["exit_code"]) and coverage["percent_covered"] >= 85
        and all(result[k] for k in ("source_unchanged_during_check", "git_unchanged", "inputs_unchanged"))
        and head == "e6738e862ece103006e1b15615b6901892cae624" and branch == "main"
        and equality["status"] == legacy["status"] == "PASS") else "FAIL"
    json_file("checks.json", result)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
