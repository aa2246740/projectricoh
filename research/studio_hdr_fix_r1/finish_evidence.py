"""Verify frozen inputs, remove this task's temporary directory, and hash delivery files."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
STUDIO = ROOT / "studio"
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-hdr-fix")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def current_source():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=STUDIO,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).decode().split("\0")
    return {name: digest(STUDIO / name) for name in names if name and (STUDIO / name).is_file()}


def verify():
    initial = json.loads((OUT / "initial_inputs.json").read_text())
    check = json.loads((OUT / "make_check.result.json").read_text())
    receipts = [json.loads(p.read_text()) for p in OUT.glob("make_check_pytest_*.json")]
    primary = max(receipts, key=lambda value: value["collected"])
    if check["exit_code"] or not check["source_unchanged"] or primary["exit_code"] or primary["rerun_max"]:
        raise SystemExit("Full check did not pass without reruns")
    source = current_source()
    changed_frozen = []
    groups = {}
    for name, sha in initial["files"].items():
        if name.startswith("studio/"):
            continue
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT):
            raise SystemExit("Frozen input resolves outside the project")
        category = "/".join(Path(name).parts[:2])
        groups[category] = groups.get(category, 0) + 1
        if not path.is_file() or digest(path) != sha:
            changed_frozen.append(name)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=STUDIO).decode().strip()
    branch = subprocess.check_output(["git", "symbolic-ref", "--short", "HEAD"], cwd=STUDIO).decode().strip()
    index_clean = not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=STUDIO)
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "frozen_groups": groups,
               "frozen_unchanged": not changed_frozen, "changed_frozen": changed_frozen,
               "source_unchanged_since_check_start": source == check["source_sha256"],
               "head": head, "head_unchanged": head == initial["head"], "branch": branch,
               "index_clean": index_clean, "source_sha256": source, "pytest": primary}
    (OUT / "input_verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["frozen_unchanged"] and receipt["source_unchanged_since_check_start"] and receipt["head_unchanged"]
    print(json.dumps({key: value for key, value in receipt.items() if key != "source_sha256"}), flush=True)


def cleanup():
    assert TMP == Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-hdr-fix")
    assert not TMP.is_symlink() and TMP.resolve() == TMP
    before = TMP.exists()
    if before:
        shutil.rmtree(TMP)
    receipt = {"utc": datetime.now(timezone.utc).isoformat(), "path": str(TMP),
               "existed_before": before, "exists_after": TMP.exists()}
    (OUT / "cleanup.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert not receipt["exists_after"]
    print(json.dumps(receipt), flush=True)


def manifest():
    source = current_source()
    files = [STUDIO / name for name in source]
    files.extend(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS" and "__pycache__" not in path.parts)
    lines = [digest(path) + "  " + str(path.relative_to(ROOT)) for path in sorted(set(files))]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(json.dumps({"files": len(lines), "manifest_sha256": digest(OUT / "SHA256SUMS")}), flush=True)


def coverage_view():
    path = OUT / "coverage.json"
    original = digest(path)
    data = json.loads(path.read_text())
    for value in data["files"].values():
        value.pop("functions", None)
        value.pop("classes", None)
    data["meta"]["detail_level"] = "lines"
    data["meta"]["full_data_file"] = "make_check.coverage"
    path.write_text(json.dumps(data) + "\n")
    receipt = {"original_json_sha256": original, "line_view_sha256": digest(path),
               "full_data_sha256": digest(OUT / "make_check.coverage"), "totals": data["totals"]}
    (OUT / "coverage_view_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"files": len(data["files"]), "coverage_percent": data["totals"]["percent_covered"]}))


if __name__ == "__main__":
    {"verify": verify, "cleanup": cleanup, "manifest": manifest, "coverage_view": coverage_view}[sys.argv[1]]()
