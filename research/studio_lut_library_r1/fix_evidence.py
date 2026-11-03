"""核对复审修复的源码、反例、零重跑收据和覆盖率。"""

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def git(*args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(["git", *args], cwd=STUDIO, env=env).decode()


def line_coverage():
    path = OUT / "fix_coverage.json"
    original = path.read_bytes()
    data = json.loads(original)
    if any("functions" in item for item in data["files"].values()):
        tables = {name: {key: value for key, value in item.items() if key != "functions"}
                  for name, item in data["files"].items()}
        removed = sum(len(item.pop("functions", {})) for item in data["files"].values())
        assert data["files"] == tables
        path.write_text(json.dumps(data, ensure_ascii=False) + "\n")
        save("fix_coverage_line_export.json", {
            "original_export_sha256": hashlib.sha256(original).hexdigest(), "line_export_sha256": sha(path),
            "removed_function_blocks": removed, "line_tables_identical": True, "totals_identical": True,
        })
    else:
        assert read("fix_coverage_line_export.json")["line_export_sha256"] == sha(path)
    return data["totals"]


def counterexamples():
    tree = ast.parse((STUDIO / "tests/test_lut_review_fix.py").read_text())
    node = next(item for item in tree.body if isinstance(item, ast.Assign) and item.targets[0].id == "REVIEW_SHA")
    expected = ast.literal_eval(node.value)
    rows = []
    for position, digest in expected.items():
        path = ROOT / f"research/review_studio_lut/attribution_{position}.original.txt"
        assert sha(path) == digest
        rows.append({"position": position, "review_file": str(path.relative_to(ROOT)), "sha256": digest,
                     "test_case": f"test_review_attribution_api_roundtrip_is_byte_identical[{position}]"})
    save("fix_counterexamples.json", {"byte_identical_to_test_inputs": True, "cases": rows})


def main():
    before = read("fix_input.json")
    run = read("fix_make_check_final.result.json")
    assert run["exit_code"] == 0 and run["source_unchanged"]
    receipts = list(OUT.glob("fix_make_check_final_pytest_*.json"))
    assert len(receipts) == 1
    tests = json.loads(receipts[0].read_text())
    assert tests["exit_code"] == tests["force_reruns"] == tests["rerun_max"] == 0
    assert tests["outcomes"] == {"passed": tests["collected"]}
    guard = read("fix_receipt_guard.result.json")
    assert guard["process_exit_code"] == 0 and guard["exit_code"] == 1 and guard["validation_error"]
    names = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    current = {name: sha(STUDIO / name) for name in names if name and (STUDIO / name).is_file()}
    assert current == run["source_sha256"]
    for label in ("fix_static_final", "fix_regression_final"):
        record = read(label + ".result.json")
        assert record["exit_code"] == 0 and record["source_unchanged"]
        assert record["source_sha256"] == current
    assert git("rev-parse", "HEAD").strip() == before["head"]
    assert git("branch", "--show-current").strip() == "main"
    assert not git("diff", "--cached", "--name-only").strip()
    assert not git("diff", "--check").strip()
    manifest = ROOT / "research/review_studio_lut/SHA256SUMS"
    assert sha(manifest) == before["review_manifest_sha256"]
    checked = 0
    for line in manifest.read_text().splitlines():
        digest, name = line.split("  ", 1)
        if name.startswith("research/review_studio_lut/"):
            assert sha(ROOT / name) == digest
            checked += 1
    counterexamples()
    baseline = read("coverage.json")["totals"]
    coverage = line_coverage()
    assert coverage["percent_covered"] >= baseline["percent_covered"]
    save("fix_coverage_comparison.json", {
        "baseline_file": "research/studio_lut_library_r1/coverage.json", "baseline_sha256": sha(OUT / "coverage.json"),
        "baseline": baseline, "final": coverage,
        "difference_percentage_points": coverage["percent_covered"] - baseline["percent_covered"], "not_lower": True,
    })
    tracked = set(git("diff", "--name-only", "-z").split("\0")) - {""}
    added = set(git("ls-files", "--others", "--exclude-standard", "-z").split("\0")) - {""}
    rows = ["status\tpath\tsha256\tbytes"]
    for name in sorted(tracked | added):
        path = STUDIO / name
        rows.append(f"{'new' if name in added else 'modified'}\tstudio/{name}\t{sha(path)}\t{path.stat().st_size}")
    (OUT / "FILE_LIST.tsv").write_text("\n".join(rows) + "\n")
    changed = sorted(name for name in current if current[name] != before["source_sha256"].get(name))
    rows = ["path\tbefore_sha256\tafter_sha256"]
    rows.extend(f"studio/{name}\t{before['source_sha256'].get(name, '-')}\t{current[name]}" for name in changed)
    (OUT / "FIX_FILE_LIST.tsv").write_text("\n".join(rows) + "\n")
    save("fix_final_evidence.json", {
        "head": before["head"], "branch": "main", "host": os.uname().sysname, "index_empty": True,
        "source_matches_full_check": True, "source_file_count": len(current), "fix_files": len(changed),
        "all_changed_files": len(tracked | added), "review_directory_files_unchanged": checked,
        "web_files_unchanged_since_r1": all(current[name] == digest for name, digest in before["source_sha256"].items() if name.startswith("web/")),
        "make_check_seconds": run["seconds"], "pytest_receipt": receipts[0].name, "pytest": tests,
        "missing_completion_receipt_is_rejected": True,
        "coverage_not_lower_than_reviewed_r1": True,
    })
    print(json.dumps({"status": "passed", "tests": tests["collected"], "coverage": coverage["percent_covered"],
                      "fix_files": len(changed), "all_changed_files": len(tracked | added)}))


if __name__ == "__main__":
    main()
