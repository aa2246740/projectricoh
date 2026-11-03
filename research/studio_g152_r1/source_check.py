"""记录检查前后的 Studio 文件与 Git 元数据摘要，读取 Git 时关闭可选锁。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(STUDIO), *args], env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}, timeout=30)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    stage = sys.argv[1]
    assert stage in ("before", "after")
    label = f"{sys.argv[2]}-" if len(sys.argv) > 2 else ""
    assert label.replace("-", "").isalnum() or not label
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    source = {name: sha(STUDIO / name) for name in sorted(set(paths)) if name and (STUDIO / name).is_file()}
    git_dir = Path(git("rev-parse", "--absolute-git-dir").decode().strip())
    metadata = {str(p.relative_to(git_dir)): sha(p) for p in sorted(git_dir.rglob("*")) if p.is_file()}
    receipt = {"source": source, "git_metadata": metadata, "head": git("rev-parse", "HEAD").decode().strip(),
               "branch": git("branch", "--show-current").decode().strip()}
    if stage == "after":
        previous = json.loads((HERE / f"source-{label}before.json").read_text())
        assert receipt == previous, "检查期间源码或 Git 元数据发生变化"
    (HERE / f"source-{label}{stage}.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"stage": stage, "files": len(source), "git_files": len(metadata), "head": receipt["head"],
                      "source_tree_sha256": hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
                      "unchanged": stage == "after"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
