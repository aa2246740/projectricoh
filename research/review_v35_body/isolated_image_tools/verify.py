#!/usr/bin/env python3
"""Replay determinism and targeted rejection cases, retaining each raw failure."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import sys

HERE = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/image_v35')
ROOT = HERE.parents[1]
LOCAL = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_v35_body/image')
NOTICE = "未审查候选，不得上卡"


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def seal(package):
    lines = [f"{sha(p.read_bytes())}  {p.relative_to(package).as_posix()}\n"
             for p in sorted(package.rglob("*")) if p.is_file() and p != package / "SHA256SUMS"]
    (package / "SHA256SUMS").write_text("".join(lines), encoding="ascii")


def fix_checksum(package):
    path = package / "candidate/SD_ROOT/ilaunch3"
    data = bytearray(path.read_bytes())
    total = 0
    for residue in range(6):
        total += (residue + 2) * sum(data[512 + residue::6])
    struct.pack_into(">I", data, 0x16c, total & 0xffffffff)
    path.write_bytes(data)
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["image_sha256"] = sha(data)
    manifest["candidate_sha256"]["ilaunch3"] = sha(data)
    dump(package / "manifest.json", manifest)


def invoke(argv, folder, label):
    result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
    (folder / (label + ".stdout.log")).write_text(result.stdout, encoding="utf-8")
    (folder / (label + ".stderr.log")).write_text(result.stderr, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--hooks", type=Path, required=True)
    parser.add_argument("--patch-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory under image_v35/local")
    args = parser.parse_args()
    output, base = args.output.resolve(), args.package.resolve()
    info = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert info.get("MountPoint") == "/Volumes/Workspace" and info.get("FilesystemType") == "apfs"
    assert info.get("VolumeUUID") == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and info.get("WritableVolume") and info.get("WritableMedia")
    assert LOCAL.resolve() == LOCAL and not LOCAL.is_symlink() and os.access(LOCAL, os.W_OK)
    assert output.is_relative_to(LOCAL) and output != LOCAL and not output.exists()
    assert base.is_relative_to(LOCAL) and base.is_dir() and not output.is_relative_to(base)
    assert args.elf.resolve().is_relative_to(ROOT) and args.hooks.resolve().is_relative_to(ROOT)
    assert args.patch_manifest.resolve().is_relative_to(ROOT)
    ignored = "firmware/image_v35/.gitignore:1:/local/ review-only output redirection"
    assert "firmware/image_v35/.gitignore:1:/local/" in ignored
    free = shutil.disk_usage(LOCAL)
    assert free.free / free.total >= 0.2, "workspace is above 80 percent usage"
    policy = json.loads((HERE / "policy.json").read_text())
    official = ROOT / "artifacts/firmware/gxr-1.51"
    stage = ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8"
    objdump = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
    protected = [*(official / n for n in policy["official"]), *(p for p in stage.rglob("*") if p.is_file()),
                 ROOT / "firmware/stage2l_switch/tools/build.py", ROOT / "firmware/stage2l_switch/tools/audit_image.py",
                 ROOT / "scripts/build_code_patch.py", ROOT / "scripts/build_drill.py",
                 objdump,
                 args.elf.resolve(), args.hooks.resolve(), args.patch_manifest.resolve(),
                 ROOT / "firmware/resident_v3/local/resident/build/resident.map",
                 *(p for name in ("firmware/image_v2", "firmware/resident_v3")
                   for p in (ROOT / name).rglob("*") if p.is_file())]
    protected = sorted(set(protected))
    before = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected}
    output.mkdir(parents=True)
    dump(output / "protected-before.json", before)
    common = ["--official", str(official / "ilaunch3"), "--elf", str(args.elf.resolve()), "--hooks", str(args.hooks.resolve()),
              "--patch-manifest", str(args.patch_manifest.resolve())]
    audit_cmd = ["/usr/bin/python3", "-I", "-B", str(Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_v35_body/isolated_image_tools/audit.py'))]
    positive = invoke(audit_cmd + common + ["--package", str(base), "--report", str(output / "positive.json"), "--verbose"], output, "positive")
    assert positive.returncode == 0, positive.stderr
    rebuilt = output / "rebuilt"
    rebuild = invoke(["/usr/bin/python3", "-I", "-B", str(Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_v35_body/isolated_image_tools/build.py')), *common, "--output", str(rebuilt)], output, "rebuild")
    assert rebuild.returncode == 0, rebuild.stderr
    left = {p.relative_to(base).as_posix(): sha(p.read_bytes()) for p in base.rglob("*") if p.is_file()}
    right = {p.relative_to(rebuilt).as_posix(): sha(p.read_bytes()) for p in rebuilt.rglob("*") if p.is_file()}
    assert left == right, "rebuild not byte-identical"
    rebuilt_audit = invoke(audit_cmd + common + ["--package", str(rebuilt), "--report", str(output / "rebuilt-audit.json")], output, "rebuilt-audit")
    assert rebuilt_audit.returncode == 0, rebuilt_audit.stderr
    parsed = ast.parse((HERE / "audit.py").read_text())
    imported = [n for node in ast.walk(parsed) if isinstance(node, ast.Import) for n in node.names]
    assert not any(n.name in ("build", "importlib", "runpy") for n in imported)
    assert not any(isinstance(node, ast.ImportFrom) and node.module and "build" in node.module for node in ast.walk(parsed))
    source_pm = json.loads(args.patch_manifest.read_text())
    built_patches = json.loads((base / "evidence/patches.json").read_text())
    assert all((p["enabled"], p["original"], p["replacement"]) == (q["enabled"], q["original"], q["replacement"])
               for p, q in zip(built_patches, source_pm)) and len(source_pm) == len(built_patches) == 37
    decoded = []
    native_decode = output / "objdump"
    native_decode.mkdir()
    image_bytes = (base / "candidate/SD_ROOT/ilaunch3").read_bytes()
    for hook in built_patches:
        if not hook["enabled"] or hook["kind"] != "BRA24":
            continue
        label = f"H{hook['number']:02}"
        raw_path = native_decode / (label + ".bin")
        raw_path.write_bytes(image_bytes[hook["file_offset"]:hook["file_offset"] + hook["length"]])
        cmd = [str(objdump), "-D", "-b", "binary", "-m", "m32r", "-EB", "--disassemble-zeroes",
               f"--adjust-vma=0x{hook['va']:x}", str(raw_path)]
        process = invoke(cmd, native_decode, label)
        observed = re.search(r"\bbra\s+0x([0-9a-fA-F]+)\b", process.stdout)
        assert process.returncode == 0 and observed and int(observed[1], 16) == hook["target"], label + " native objdump target differs"
        decoded.append(dict(hook=label, va=hook["va"], symbol=hook["target_symbol"],
                            decoded_target=int(observed[1], 16), pass_decode=True, argv=cmd))
    assert len(decoded) == 7
    dump(native_decode / "decoded.json", decoded)
    cases = [
        ("outside-byte-valid-checksum", "E_OUTSIDE_DIFF"),
        ("wrong-branch-target-valid-checksum", "E_HOOK_TARGET"),
        ("wrong-container-checksum", "E_CHECKSUM"),
        ("payload-overflow-elf", "E_PAYLOAD_RANGE"),
        ("wrong-recovery-file", "E_RECOVERY"),
        ("disabled-hook-valid-checksum", "E_DISABLED_HOOK"),
        ("stock-data-valid-checksum", "E_STOCK_DATA"),
        ("payload-byte-valid-checksum", "E_PAYLOAD_BYTES"),
        ("ff-gap-byte-valid-checksum", "E_PAYLOAD_BYTES"),
        ("wrong-original-hook-source", "E_HOOK_ORIGINAL"),
        ("header-descriptor-byte", "E_HEADER"),
        ("wrong-normalized-elf", "E_ELF_NORMALIZATION"),
        ("wrong-package-sum", "E_SUMS"),
        ("deleted-H15-valid-checksum", "E_DISABLED_HOOK"),
    ]
    results = []
    for name, expected in cases:
        folder = output / name
        folder.mkdir()
        package = folder / "package"
        shutil.copytree(base, package)
        image = package / "candidate/SD_ROOT/ilaunch3"
        data = bytearray(image.read_bytes())
        changed_file, offset = str(image.relative_to(folder)), None
        changed_original = sha(data)
        use_elf, use_hooks = args.elf.resolve(), args.hooks.resolve()
        resealed, fixed = True, False
        if name == "outside-byte-valid-checksum":
            offset = 0x200
            data[offset] ^= 1
        elif name == "wrong-branch-target-valid-checksum":
            offset = built_patches[0]["file_offset"] + 3
            data[offset] ^= 1
        elif name == "wrong-container-checksum":
            offset = 0x16c
            data[offset] ^= 1
        elif name == "payload-overflow-elf":
            changed_file = "oversize.elf"
            use_elf = folder / changed_file
            mutated = bytearray(args.elf.read_bytes())
            shoff = struct.unpack_from(">I", mutated, 32)[0]
            offset = shoff + 40 + 20
            struct.pack_into(">I", mutated, offset, policy["window_end"] - policy["window_start"] + 4)
            use_elf.write_bytes(mutated)
            (package / "evidence/resident.source.elf").write_bytes(mutated)
            changed_original = sha(args.elf.read_bytes())
        elif name == "wrong-recovery-file":
            changed_file = "package/recovery-official-1.51/SD_ROOT/ilaunch3"
            target = folder / changed_file
            damaged = bytearray(target.read_bytes())
            offset = 512
            damaged[offset] ^= 1
            target.write_bytes(damaged)
        elif name in ("disabled-hook-valid-checksum", "stock-data-valid-checksum", "deleted-H15-valid-checksum"):
            number = 15 if name.startswith("deleted") else 24 if name.startswith("disabled") else 3
            offset = built_patches[number - 1]["file_offset"]
            if name.startswith("deleted"):
                assert not built_patches[number - 1]["enabled"]
            data[offset] ^= 1
        elif name == "payload-byte-valid-checksum":
            offset = 0x796c + 128
            data[offset] ^= 1
        elif name == "ff-gap-byte-valid-checksum":
            offset = 0x796c + json.loads((base / "manifest.json").read_text())["code_bytes"]
            data[offset] ^= 1
        elif name == "wrong-original-hook-source":
            changed_file = "hooks-wrong-original.json"
            use_hooks = folder / changed_file
            h = json.loads(args.hooks.read_text())
            h[0]["original_bytes"] = "00" + h[0]["original_bytes"][2:]
            dump(use_hooks, h)
            (package / "evidence/hooks.source.json").write_bytes(use_hooks.read_bytes())
            changed_original = sha(args.hooks.read_bytes())
        elif name == "header-descriptor-byte":
            offset = 0x20
            data[offset] ^= 1
        elif name == "wrong-normalized-elf":
            changed_file = "package/evidence/resident.load.elf"
            target = folder / changed_file
            damaged = bytearray(target.read_bytes())
            changed_original = sha(damaged)
            offset = 16
            damaged[offset] ^= 1
            target.write_bytes(damaged)
        elif name == "wrong-package-sum":
            changed_file = "package/SHA256SUMS"
            target = folder / changed_file
            changed_original = sha(target.read_bytes())
            text = target.read_text()
            target.write_text(("0" if text[0] != "0" else "1") + text[1:])
            offset, resealed = 0, False
        image.write_bytes(data)
        if name.endswith("valid-checksum"):
            fix_checksum(package)
            fixed = True
        if resealed:
            seal(package)
        cmd = audit_cmd + ["--official", str(official / "ilaunch3"), "--elf", str(use_elf), "--hooks", str(use_hooks),
                           "--patch-manifest", str(args.patch_manifest.resolve()),
                           "--package", str(package), "--report", str(folder / "audit.json")]
        run = invoke(cmd, folder, "audit")
        observed = json.loads((folder / "audit.json").read_text())
        passed = run.returncode == 1 and observed.get("code") == expected
        record = dict(case=name, pass_rejection=passed, expected=expected, observed=observed,
                      returncode=run.returncode, argv=cmd, changed_file=changed_file, offset=offset,
                      original_sha256=changed_original, mutated_sha256=sha((folder / changed_file).read_bytes()),
                      checksum_repaired=fixed, package_sums_resealed=resealed)
        if name == "payload-overflow-elf":
            build = invoke(["/usr/bin/python3", "-I", "-B", str(Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_v35_body/isolated_image_tools/build.py')), "--official", str(official / "ilaunch3"),
                            "--elf", str(use_elf), "--hooks", str(args.hooks.resolve()),
                            "--patch-manifest", str(args.patch_manifest.resolve()),
                            "--output", str(folder / "refused-build")], folder, "build")
            record["builder_rejected_before_output"] = build.returncode == 1 and "E_PAYLOAD_RANGE" in build.stderr and not (folder / "refused-build").exists()
            passed = passed and record["builder_rejected_before_output"]
            record["pass_rejection"] = passed
        dump(folder / "case.json", record)
        results.append(record)
        assert passed, name + ": " + run.stderr
    after = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in protected}
    dump(output / "protected-after.json", after)
    assert before == after, "read-only protected inputs changed during verification"
    summary = dict(status="VERIFICATION_PASS", image_sha256=sha((base / "candidate/SD_ROOT/ilaunch3").read_bytes()),
                   deterministic_package_files=len(left), deterministic_identical=True,
                   raw_source_patch_manifest_matches=True, audit_imports_builder=False,
                   objdump_branch_targets=decoded, objdump_sha256=sha(objdump.read_bytes()),
                   rejections=results, rejection_count=len(results), protected_inputs_unchanged=len(before),
                   python_executable=sys.executable, volume={k: info[k] for k in ("MountPoint", "VolumeUUID", "FilesystemType", "WritableVolume", "WritableMedia")},
                   camera_executed=False, sd_accessed=False)
    dump(output / "verification.json", summary)
    print(f"VERIFICATION_PASS deterministic_files={len(left)} rejections={len(results)}/{len(cases)} objdump_branches={len(decoded)} protected_unchanged={len(before)}")
    for result in results:
        print(result["case"] + ": " + result["observed"]["code"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
