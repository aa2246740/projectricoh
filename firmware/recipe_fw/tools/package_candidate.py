#!/usr/bin/env python3
"""Package the reviewed experiment inside this project; never copy to a card."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
PACKAGES = ROOT / "artifacts/stage1b-candidate/packages"
DEFAULT_REVIEW = ROOT / "research/review/STAGE1B_RESIDENT_REVIEW_R2_GPT61.json"
NATIVE_GATES_SCOPE = "Native activity gates, host and static evidence only"
spec = importlib.util.spec_from_file_location("gxr_recipe_image_audit", HERE / "tools/audit_image.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
require = audit.require


def sha(data):
    return hashlib.sha256(data).hexdigest()


def approved_review(review, payload, hooks_sha256):
    require(review["status"] == "PASS" and not review["blocking_findings"], "Host review has not passed")
    require(review["payload_sha256"] == sha(payload) and review["payload_bytes"] == len(payload),
            "Host review belongs to a different payload")
    require(review["scope"] in ("R1 fixes, host and static evidence only", NATIVE_GATES_SCOPE)
            and not review["camera_executed"],
            "Unexpected review scope")
    if review["scope"] == NATIVE_GATES_SCOPE:
        require(review.get("hooks_sha256") == hooks_sha256, "Host review belongs to different hooks")


def destination(name):
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", name) is not None, "Use a plain package name")
    path = (PACKAGES / name).resolve()
    require(path.is_relative_to(ROOT) and path.parent == PACKAGES.resolve(), "Package escapes project")
    require(not path.exists(), "Refusing to overwrite an existing package")
    return path


def prepare(review_path=DEFAULT_REVIEW):
    files, hooks, payload, symbols = audit.read_inputs()
    review_path = review_path.resolve()
    require(review_path.is_relative_to(ROOT), "Review escapes project")
    review = json.loads(review_path.read_text())
    approved_review(review, payload, sha((HERE / "build/hooks.json").read_bytes()))
    review_report = (ROOT / review["report"]).resolve()
    require(review_report.is_relative_to(ROOT), "Review report escapes project")
    review_text = review_report.read_bytes()
    report = audit.audit(files, hooks, payload, symbols)
    image = bytearray(files["ilaunch3"])
    for hook in hooks["hooks"]:
        start = int(hook["file_offset"], 16)
        image[start:start + hook["length"]] = bytes.fromhex(hook["new_bytes"])
    p = hooks["payload_patch"]
    start = int(p["file_offset"], 16)
    image[start:start + len(payload)] = payload
    struct.pack_into(">I", image, 0x16c, int(report["checksum"], 16))
    require(sha(image) == report["candidate_image_sha256"], "Packaging differs from the audited image")
    candidate = dict(files)
    candidate["ilaunch3"] = bytes(image)
    make = audit.module("gxr_recipe_make", HERE / "tools/make_recipes.py")
    recipe_source = (HERE / "tools/validation_recipes_16.json").read_bytes()
    recipes = make.compile_recipes(json.loads(recipe_source))
    require(recipes == (HERE / "build/validation-RECIPES0.DAT").read_bytes(), "Recipe library differs from host-tested bytes")
    return files, candidate, review, report, recipe_source, recipes, review_text


def write_tree(root, files):
    root.mkdir(parents=True)
    for name, data in sorted(files.items()):
        (root / name).write_bytes(data)
    sums = "".join(f"{sha(data)}  {name}\n" for name, data in sorted(files.items()))
    (root.parent / "SHA256SUMS").write_text(sums)
    require({p.name for p in root.iterdir()} == set(files), "Written component list differs")
    for name, data in files.items():
        require((root / name).read_bytes() == data, f"Readback differs: {name}")
    require((root.parent / "SHA256SUMS").read_text() == sums, "Written checksums differ")


def write_package(path, prepared):
    require(path.resolve() == destination(path.name), "Writes must stay in the local package directory")
    files, candidate, review, report, recipe_source, recipes, review_text = prepared
    path.mkdir(parents=True, exist_ok=False)
    write_tree(path / "candidate/SD_ROOT", candidate)
    write_tree(path / "recovery-official-1.51/SD_ROOT", files)
    library = path / "recipe-library"
    library.mkdir()
    (library / "RECIPES0.DAT").write_bytes(recipes)
    (library / "recipes-16-validation.json").write_bytes(recipe_source)
    require((library / "RECIPES0.DAT").read_bytes() == recipes, "Written recipes differ")
    evidence = path / "evidence"
    evidence.mkdir()
    for name, data in (("image-audit.json", report), ("host-review.json", review)):
        (evidence / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    for source, name in ((HERE / "build/manifest.json", "build-manifest.json"),
                         (HERE / "build/hooks.json", "hooks.json"),
                         (HERE / "build/verification.json", "host-verification.json"),
                         (HERE / "build/abi-tests.json", "abi-model-tests.json")):
        (evidence / name).write_bytes(source.read_bytes())
    (evidence / "host-review.md").write_bytes(review_text)
    readme = """# GXR A12 50mm：16 配方实验候选

本包供一次真机功能验收，尚未在相机运行。先核对本包并确认本次刷写，再准备 SD 卡。

- 配方通过 ADJ 列表选择，使用原厂 Setting1 色彩参数与白平衡偏移。
- 当前支持电脑编辑配方文件。相机内编辑、保存界面尚未接入。
- 附带 16 槽功能验收库，名称和参数用于检查每槽独立调用；它们还不是调校好的 16 种胶片风格。
- 本包仅改变机身 ilaunch3。其余 28 个组件文件，包括 A12 50mm 固件，保持官方原样。
- 当前 payload 的真实执行、页面绘制、关机后状态以及 JPEG+DNG 配对均待真机验证。
- 以前的探针刷回官方 1.51 已成功。若这份新代码导致主程序无法运行，能否再次进入更新界面仍未证明；恢复文件不保证救砖。

目录：

- candidate/SD_ROOT：29 个候选升级文件。
- recovery-official-1.51/SD_ROOT：29 个逐字节未改的官方 1.51 文件。
- recipe-library/RECIPES0.DAT：1056 B 的 16 槽功能验收库。
- recipe-library/recipes-16-validation.json：电脑可编辑的配方源文件。
- evidence：源码与工具哈希、电脑测试、独立审查及镜像审计。

以上均保存在电脑，未复制到卡。候选和恢复目录必须分开使用。相机仍由用户按键完成实际刷写。
"""
    (path / "README.md").write_text(readme)
    manifest = {
        "status": "EXPERIMENTAL_NOT_CAMERA_TESTED", "package_name": path.name,
        "package_builder_sha256": sha(Path(__file__).read_bytes()),
        "payload_sha256": report["payload_sha256"], "payload_bytes": report["payload_bytes"],
        "candidate_sha256": {n: sha(d) for n, d in sorted(candidate.items())},
        "recovery_sha256": {n: sha(d) for n, d in sorted(files.items())},
        "recipe_library_sha256": sha(recipes), "recipe_source_sha256": sha(recipe_source),
        "modified_component_files": [n for n in files if files[n] != candidate[n]],
        "written_and_reverified": True, "upgrade_package_generated": True,
        "camera_executed": False, "flash_authorized": False, "sd_accessed": False,
        "unconditional_recovery_verified": False,
        "evidence_sha256": {str(p.relative_to(path)): sha(p.read_bytes()) for p in sorted(evidence.iterdir())},
    }
    # A complete manifest is the last write, after all upgrade files pass readback.
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write a new local experimental package")
    parser.add_argument("--name", help="Defaults to the verified payload hash")
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW,
                        help="Independent host review JSON matching this payload and hook set")
    args = parser.parse_args()
    prepared = prepare(args.review)
    path = destination(args.name or "stage1b-16-recipes-" + prepared[3]["payload_sha256"][:12])
    if args.write:
        result = write_package(path, prepared)
        print(json.dumps({"package": str(path), "status": result["status"],
                          "candidate_ilaunch3_sha256": result["candidate_sha256"]["ilaunch3"],
                          "written_and_reverified": True}, ensure_ascii=False))
    else:
        print(json.dumps({"status": "READY_TO_WRITE_LOCAL_EXPERIMENT", "output": str(path),
                          "image_sha256": prepared[3]["candidate_image_sha256"]}, ensure_ascii=False))
