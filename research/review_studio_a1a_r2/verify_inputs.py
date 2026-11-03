"""复核冻结文件与只读 Git 状态，并保存本轮收据。"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
BASE = OUT.parent.parent
REPO = BASE / "studio"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="input-after")
    args = parser.parse_args()
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    def git(*values):
        return subprocess.check_output(["git", "-C", str(REPO), *values], env=env)
    before = json.loads((OUT / "source-before.json").read_text())
    current_names = set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0"))
    current_names.discard("")
    current = {name: sha(REPO / name) for name in sorted(current_names) if (REPO / name).is_file()}
    source_changes = sorted(name for name in set(before) | set(current) if before.get(name) != current.get(name))
    manifest_changes = []
    count = 0
    for line in (BASE / "research/studio_a1a_r1_fix/SHA256SUMS").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        count += 1
        if sha(BASE / name) != expected:
            manifest_changes.append(name)
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    result = {"checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "head": git("rev-parse", "HEAD").decode().strip(),
              "source_files": len(current), "source_changes": source_changes,
              "manifest_entries": count, "manifest_changes": manifest_changes,
              "manifest_sha256": sha(BASE / "research/studio_a1a_r1_fix/SHA256SUMS"),
              "git_status_unchanged": status == (OUT / "git-status-before.txt").read_bytes()}
    (OUT / (args.name + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (OUT / (args.name + "-git-status.txt")).write_bytes(status)
    print(json.dumps(result, ensure_ascii=False))
    assert not source_changes and not manifest_changes and result["git_status_unchanged"]
    assert result["head"] == "1407830ee7c32fff892b23f2ddbfeb2bafd95b45"
    assert result["manifest_sha256"] == "ced2bb332f98cc254fe7425f0cb926645bfb6306f8ed6104e389b09dcb743766"


if __name__ == "__main__":
    main()
