"""收尾：再核对冻结输入，删除本轮临时目录，填写用时并生成摘要清单。"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

OUT = Path(__file__).resolve().parent
BASE = OUT.parent.parent
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r2")

volume = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
assert volume.get("VolumeUUID", volume.get("DiskUUID")) == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
assert volume.get("FilesystemType") == "apfs" and volume.get("WritableVolume") is True
assert TEMP.resolve() == TEMP and not TEMP.is_symlink()

env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", TMPDIR=str(TEMP), PYTHONDONTWRITEBYTECODE="1")
subprocess.run([sys.executable, "-I", "-B", str(OUT / "verify_inputs.py")], env=env, check=True, capture_output=True)
inputs = json.loads((OUT / "input-after.json").read_text())
summary = json.loads((OUT / "independent-summary.json").read_text())
assert summary["total"] == 147 and summary["passed"] == 127 and summary["failed"] == 20
events = [json.loads(line) for line in (OUT / "make-check-results.jsonl").read_text().splitlines()]
assert sum(row["when"] == "call" and row["outcome"] == "passed" for row in events) == 632
assert not [row for row in events if row["outcome"] in {"failed", "rerun"}]
assert (OUT / "REVIEW.md").read_text().splitlines()[0] == "修改后再提交"

existed = TEMP.exists()
if existed:
    shutil.rmtree(TEMP)
assert not TEMP.exists()

started = datetime.datetime.fromisoformat("2026-10-31T18:18:54+00:00")
finished = datetime.datetime.now(datetime.timezone.utc)
elapsed = (finished - started).total_seconds()
minutes, seconds = divmod(int(elapsed), 60)
local = datetime.timezone(datetime.timedelta(hours=8))
duration = f"{minutes} 分 {seconds} 秒（{started.astimezone(local):%Y-%m-%d %H:%M:%S} 至 {finished.astimezone(local):%Y-%m-%d %H:%M:%S}，UTC+8）"
report = (OUT / "REVIEW.md").read_text()
assert "REVIEW_DURATION" in report
(OUT / "REVIEW.md").write_text(report.replace("REVIEW_DURATION", duration))
receipt = {"started_utc": started.isoformat(), "finished_utc": finished.isoformat(),
           "elapsed_seconds": round(elapsed, 3), "temporary_directory": str(TEMP),
           "temporary_directory_existed": existed, "temporary_directory_removed": not TEMP.exists(),
           "volume_uuid": volume.get("VolumeUUID", volume.get("DiskUUID")),
           "source_files_unchanged": inputs["source_files"], "frozen_manifest_matches": inputs["manifest_entries"],
           "git_status_unchanged": inputs["git_status_unchanged"],
           "make_check_passed": 632, "make_check_reruns": 0,
           "independent": summary, "verdict": "修改后再提交"}
(OUT / "final-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

manifest = OUT / "SHA256SUMS"
paths = sorted(path for path in OUT.rglob("*") if path.is_file() and path != manifest)
lines = []
for path in paths:
    assert not path.is_symlink()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append(f"{sha}  {path.relative_to(BASE).as_posix()}")
manifest.write_text("\n".join(lines) + "\n")
for line in manifest.read_text().splitlines():
    expected, rel = line.split(maxsplit=1)
    assert hashlib.sha256((BASE / rel).read_bytes()).hexdigest() == expected
print(json.dumps({"verdict": receipt["verdict"], "elapsed_seconds": receipt["elapsed_seconds"],
                  "temporary_directory_removed": receipt["temporary_directory_removed"],
                  "manifest_entries": len(paths), "manifest_verified": True,
                  "report_sha256": hashlib.sha256((OUT / "REVIEW.md").read_bytes()).hexdigest()}, ensure_ascii=False))
