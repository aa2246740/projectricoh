"""核对冻结输入、样本及结果，清理指定临时目录，生成完整摘要清单。"""

from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
BASE = OUT.parent.parent
REPO = BASE / "studio"
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(name):
    return json.loads((OUT / name).read_text())


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, env=dict(os.environ, GIT_OPTIONAL_LOCKS="0")).decode()


volume = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
assert volume.get("VolumeUUID", volume.get("DiskUUID")) == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
assert volume.get("FilesystemType") == "apfs" and volume.get("WritableVolume") is True
assert OUT == BASE / "research/review_studio_a1a_r3"
assert TEMP.is_dir() and not TEMP.is_symlink()

before = read_json("source-before.json")
current_names = set(git("ls-files", "-c", "-o", "--exclude-standard", "-z").split("\0"))
current = {name: sha(REPO / name) for name in sorted(current_names) if name and (REPO / name).is_file()}
assert current == before
assert git("status", "--short", "--untracked-files=all") == (OUT / "git-status-before.txt").read_text()
assert git("rev-parse", "HEAD").strip() == "1407830ee7c32fff892b23f2ddbfeb2bafd95b45"
old = BASE / "research/review_studio_a1a_r2"
prior = {str(path.relative_to(old)): sha(path) for path in old.rglob("*") if path.is_file()}
assert prior == read_json("previous-before.json")
for entry in read_json("input-receipt.json")["manifests"]:
    assert sha(BASE / entry["manifest"]) == entry["manifest_sha256"]
    for row in entry["files"]:
        assert sha(BASE / row["path"]) == row["sha256"]

rows = read_json("observations-final.json")
samples = {}
for row in rows:
    if row["case"] == "sample_inventory":
        for entry in row["files"]:
            samples["captures/street-g137-20261031/dng/" + entry["name"]] = entry
    if row["case"] == "sample_inventory_additional":
        samples[row["sample"]] = row
for name, entry in samples.items():
    path = BASE / name
    st = path.stat()
    assert sha(path) == entry["sha256"]
    assert st.st_mtime_ns == entry["mtime_ns"] and st.st_ctime_ns == entry["ctime_ns"]

calls = [json.loads(line) for line in (OUT / "make-check-results.jsonl").read_text().splitlines()]
assert Counter(row["outcome"] for row in calls if row["when"] == "call") == {"passed": 681}
assert not any(row["outcome"] == "rerun" for row in calls)
assert max(Counter(row["nodeid"] for row in calls if row["when"] == "call").values()) == 1
new_calls = [json.loads(line) for line in (OUT / "new-tests-final-results.jsonl").read_text().splitlines()]
assert Counter(row["outcome"] for row in new_calls if row["when"] == "call") == {"passed": 27, "failed": 14}
failed = [row["nodeid"] for row in new_calls if row["when"] == "call" and row["outcome"] == "failed"]
assert sum("test_startup_" in name for name in failed) == 4
assert sum("test_archive_in_first_stream" in name or "test_system_gzip" in name for name in failed) == 9
assert sum("test_write_checks_directory_after_open_before_bytes" in name for name in failed) == 1
assert len(read_json("ui-results.json")) == 7
assert read_json("package-audit.json")["hits"] == []

exports = []
for row in rows:
    if row["case"] != "real_camera_render":
        continue
    path = TEMP / "pytest-new-tests-final/test_real_mount_and_50mm_paths0" / row["unit"] / "exports/R0000001_gxr_neutral.jpg"
    assert sha(path) == row["export_sha256"]
    exports.append({"unit": row["unit"], "sha256": row["export_sha256"], "size": path.stat().st_size,
                    "dimensions": row["export_size"], "visually_checked": True})
assert len(exports) == 2

shutil.rmtree(TEMP)
assert not TEMP.exists()
ended = datetime.now(timezone.utc)
started = datetime.fromisoformat(read_json("input-receipt.json")["started_utc"])
elapsed = (ended - started).total_seconds()
local = timezone(timedelta(hours=8))
interval = started.astimezone(local).strftime("2026-11-01 %H:%M:%S") + " 至 " + ended.astimezone(local).strftime("%H:%M:%S") + "，UTC+8"
duration = f"{int(elapsed // 60)} 分 {elapsed % 60:.1f} 秒"
report = (OUT / "REVIEW.md").read_text()
assert report.startswith("修改后再提交\n")
report = report.replace("{{review_interval}}", interval).replace("{{review_elapsed}}", duration)
assert "{{review_" not in report
(OUT / "REVIEW.md").write_text(report)
receipt = {"started_utc": started.isoformat(), "ended_utc": ended.isoformat(), "elapsed_seconds": round(elapsed, 3),
           "source_files_unchanged": len(current), "previous_files_unchanged": len(prior),
           "manifest_files_unchanged": [63, 94], "git_status_and_head_unchanged": True,
           "sample_files_unchanged": len(samples), "exports_checked_before_cleanup": exports,
           "temporary_directory": str(TEMP), "temporary_directory_removed": True,
           "verdict": "修改后再提交", "p1_groups": 2, "p2_items": 1}
write_json("final-receipt.json", receipt)
files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
(OUT / "SHA256SUMS").write_text("".join(f"{sha(path)}  {path.relative_to(BASE).as_posix()}\n" for path in files))
print(json.dumps({**receipt, "manifest_count": len(files)}, ensure_ascii=False))
