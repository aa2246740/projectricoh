"""Verify the fence and remove this review's one disposable directory."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
from run_checks import manifest

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2")


def main():
    volume = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert volume["MountPoint"] == "/Volumes/Workspace" and volume["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"]
    assert SCRATCH.resolve() == SCRATCH and SCRATCH.name == "review-studio-v2"
    ready = json.loads((SCRATCH / "server-ready.json").read_text())
    proc = subprocess.run(["ps", "-p", str(ready["pid"]), "-o", "command="], capture_output=True, text=True)
    server_stopped = proc.returncode != 0 or "review_studio_v2/temp_server.py" not in proc.stdout
    assert server_stopped, "Stop the review temp_server.py before cleanup"
    commands = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
    remaining = [line for line in commands.splitlines()
                 if "chrome-headless-shell" in line and f"--user-data-dir={SCRATCH}/" in line]
    assert not remaining, remaining
    initial = json.loads((HERE / "source_manifest.json").read_text())
    source_unchanged = manifest() == initial
    media = json.loads((HERE / "baseline-fixture.json").read_text())["photos"]
    bad_media = [item["relpath"] for photo in media.values() for item in photo["media"].values()
                 if hashlib.sha256((SCRATCH / "library" / item["relpath"]).read_bytes()).hexdigest() != item["sha256"]]
    firmware = json.loads((HERE / "acceptance.json").read_text())["firmware"]
    bad_firmware = []
    for gen, rel in (("137", "firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT"),
                     ("138", "firmware/package_v38_g138/SD_ROOT/GXRCE.DAT")):
        if hashlib.sha256((STUDIO.parent / rel).read_bytes()).hexdigest() != firmware[gen]["sha256"]:
            bad_firmware.append(gen)
    assert source_unchanged and not bad_media and not bad_firmware
    shutil.rmtree(SCRATCH)
    result = {"time": datetime.now().astimezone().isoformat(), "source_unchanged": source_unchanged,
              "source_files": len(initial), "media_unchanged": not bad_media,
              "firmware_unchanged": not bad_firmware, "server_stopped": server_stopped,
              "server_pid": ready["pid"], "server_port": ready["port"], "browser_stopped": not remaining,
              "scratch_removed": not SCRATCH.exists()}
    (HERE / "cleanup.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
