"""Create a v1 library using only source read by git show, outside the repository."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"
PROJECT = STUDIO.parent
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2")


def prepare() -> None:
    for name in ("library", "app-home", "exports", "volumes"):
        path = SCRATCH / name
        if path.exists():
            shutil.rmtree(path)
    source = SCRATCH / "baseline"
    files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "e6952ac", "--", "src"], cwd=STUDIO).decode().splitlines()
    for name in files:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(["git", "show", f"e6952ac:{name}"], cwd=STUDIO))
    env = os.environ.copy()
    env.update(TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(STUDIO / ".venv/bin/python"), "-B", str(__file__), "--create"],
                            cwd=source, env=env, capture_output=True, text=True, timeout=240)
    (HERE / "baseline.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout, end="")


def create() -> None:
    sys.path.insert(0, str(SCRATCH / "baseline/src"))
    from PIL import Image
    import numpy as np
    import gxr_studio
    from gxr_studio import audit
    from gxr_studio.cards.discovery import Card
    from gxr_studio.cards.importer import run_import, ImportOptions
    from gxr_studio.library.store import Library
    from gxr_studio.library.edits import write_crop
    from gxr_studio.render.edits import write
    from gxr_studio.render.recipes import Menu
    audit.forbid_volumes()
    audit.forbid_network()
    for path in (Path.home() / "Pictures/GXR Studio", Path.home() / "Pictures/GXR 导出",
                 Path.home() / "Library/Application Support/GXR Studio"):
        audit.protect(path)
        audit.forbid_reads(path)
    card = SCRATCH / "volumes/REVIEW/DCIM/100RICOH"
    card.mkdir(parents=True, exist_ok=True)
    daily = PROJECT / "captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228"
    for name in ("R8051219.DNG", "R8051219.JPG", "R8051221.JPG"):
        shutil.copyfile(daily / name, card / name)
    checker = PROJECT / "captures/a12-50/2026-10-19/stage2d-colorchecker"
    for name in ("R8051148.DNG", "R8051148.JPG"):
        shutil.copyfile(checker / name, card / name)
    yy, xx = np.mgrid[0:480, 0:640]
    rgb = np.stack([(xx * 140 / 640 + 30), (yy * 140 / 480 + 30), (np.sin(xx / 28) * 35 + 90)], axis=-1).astype(np.uint8)
    Image.fromarray(rgb).save(card / "REVIEW.JPG", quality=97)
    Image.fromarray(rgb).save(card / "PORTRAIT.JPG", quality=97, exif=Image.Exif())
    lib = Library(SCRATCH / "library").open()
    try:
        progress = run_import(lib, Card(root=card.parents[1], label="REVIEW"), ImportOptions(min_free_bytes=0, make_thumbs=False))
        assert progress.state == "done", progress.to_dict()
        saved = {}
        for shot in lib.list_shots():
            sid = shot["shot_id"]
            if shot["name"] == "R8051219":
                write_crop(lib, shot, preset="1:1", rect=None, angle_deg=3.5)
                write(lib, shot, {"recipe": {"unit": "jlaunch", "slot": 8, "levels": {},
                                            "memory": {"jlaunch/8": {"contrast": 1}}},
                                 "adjust": {"exposure_ev": 0.5, "wb": {"warm": 15, "tint": -10}, "contrast": 20},
                                 "curve": {"master": [[0, 0], [100, 80], [255, 255]]}}, Menu())
            elif shot["name"] == "R8051221":
                write_crop(lib, shot, preset="16:9", rect=None, angle_deg=-2)
                write(lib, shot, {"adjust": {"exposure_ev": 1.0}}, Menu())
            side, _ = lib.read_sidecar_or_default(shot)
            saved[shot["name"]] = {"id": sid, "sidecar": side,
                "media": {kind: {"relpath": item["relpath"], "sha256": item["sha256"]} for kind, item in shot["files"].items()}}
        result = {"baseline": "e6952acb89de95e089c8e7080c5d92de99057cc4", "module": gxr_studio.__file__,
                  "photos": saved, "imported_shots": progress.imported_shots}
        (HERE / "baseline-fixture.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"module": gxr_studio.__file__, "photos": len(saved), "state": progress.state}))
    finally:
        lib.close()


if __name__ == "__main__":
    create() if "--create" in sys.argv else prepare()
