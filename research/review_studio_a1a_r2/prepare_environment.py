"""只复制离线构建后端缓存，检查工具的缓存也放在指定临时目录。"""

from pathlib import Path
import shutil
import json
import plistlib
import subprocess

OUT = Path(__file__).resolve().parent
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r2")
SOURCE_CACHE = Path("/Users/wu/.cache/uv")
volume = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
assert volume.get("VolumeUUID", volume.get("DiskUUID")) == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
assert volume.get("FilesystemType") == "apfs" and volume.get("WritableVolume") is True
for directory in (TEMP, *(TEMP / name for name in ("home", "cache", "bin", "uv", "mypy", "ruff"))):
    directory.mkdir(parents=True, exist_ok=True)
names = {"hatchling", "packaging", "pathspec", "pluggy", "tomlkit", "trove-classifiers", "trove_classifiers"}
copied = []
for index in (SOURCE_CACHE / "wheels-v5").iterdir():
    if not index.is_dir():
        continue
    for name in names:
        source = index / name
        if not source.is_dir():
            continue
        destination = TEMP / "uv" / source.relative_to(SOURCE_CACHE)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        for child in source.iterdir():
            if child.is_symlink() and child.resolve().is_dir():
                archive = TEMP / "uv" / "archive-v0" / child.resolve().name
                shutil.copytree(child.resolve(), archive, dirs_exist_ok=True)
                copied.append(str(child.resolve()))
                item = destination / child.name
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                elif item.is_symlink():
                    item.unlink()
                item.symlink_to(archive, target_is_directory=True)
        copied.append(str(source))
for name in names:
    for source in (SOURCE_CACHE / "simple-v17" / "pypi").glob(name + ".*"):
        destination = TEMP / "uv" / source.relative_to(SOURCE_CACHE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(source))
wrapper = TEMP / "bin" / "uv"
wrapper.write_text('''#!/bin/sh
if [ "$1" = "run" ] && [ "$2" = "--frozen" ] && [ "$3" = "lint-imports" ]; then
    shift 3
    exec /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.venv/bin/lint-imports --cache-dir /Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-a1a-r2/imports "$@"
fi
exec /opt/homebrew/bin/uv "$@"
''')
wrapper.chmod(0o700)
(OUT / "offline-cache.json").write_text(json.dumps(copied, indent=2) + "\n")
print("copied", len(copied), "cache entries")
