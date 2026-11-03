"""核对卷与本任务进程后，删除指定的临时目录并保存清理回执。"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1")


def main() -> None:
    receipt_name = sys.argv[1] if len(sys.argv) > 1 else "cleanup.json"
    assert Path(receipt_name).name == receipt_name and receipt_name.endswith(".json")
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"], timeout=30))
    assert info["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert info["FilesystemType"] == "apfs" and info["MountPoint"] == "/Volumes/Workspace" and info["Writable"]
    assert SCRATCH.is_dir() and not SCRATCH.is_symlink() and SCRATCH.resolve() == SCRATCH
    lines = subprocess.check_output(["ps", "-axo", "pid=,ppid=,args="], text=True, timeout=30).splitlines()
    processes = {}
    for line in lines:
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            processes[int(fields[0])] = (int(fields[1]), fields[2])
    ancestors = set()
    pid = os.getpid()
    while pid in processes and pid not in ancestors:
        ancestors.add(pid)
        pid = processes[pid][0]
    markers = (str(SCRATCH), str(HERE), "/studio_g152_r1/", "/studio-g152-r1/")
    remaining = [{"pid": pid, "command": command} for pid, (_, command) in processes.items()
                 if pid not in ancestors and any(marker in command for marker in markers)]
    assert not remaining, remaining
    clones = [str(p.relative_to(SCRATCH)) for p in SCRATCH.rglob("*code_sign_clone*")]
    shutil.rmtree(SCRATCH)
    assert not SCRATCH.exists()
    receipt = {"volume_uuid": info["VolumeUUID"], "filesystem": info["FilesystemType"], "writable": info["Writable"],
               "remaining_task_processes": remaining, "code_sign_clone_removed": clones, "scratch_deleted": True}
    (HERE / receipt_name).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
