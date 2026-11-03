"""Run the original v3.6 verifier with only isolated output routing changed."""
import os
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, save
from subprocess import run

source = ROOT / "firmware/image_v36"
local = HERE / "image"
base = local / "base"
assert not base.exists()
shutil.copytree(source / "local/body-v36", base)
argv = ["/usr/bin/python3", "-I", "-B", str(HERE / "isolated_image_tools/verify.py"),
        "--package", str(base), "--elf", str(HERE / "resident/build/resident.elf"),
        "--hooks", str(source / "local/hooks-v36.json"),
        "--patch-manifest", str(ROOT / "firmware/resident_v36/local/resident/patch-manifest.json"),
        "--output", str(local / "verification")]
save("image-verify-command.json", argv)
raise SystemExit(run(argv, cwd=ROOT, env=dict(os.environ, TMPDIR=str(HERE / "tmp"))).returncode)
