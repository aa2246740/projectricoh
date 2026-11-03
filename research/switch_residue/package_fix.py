#!/usr/bin/env python3
"""Package tested selection fixes locally; never access removable camera media."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "firmware/stage2l_switch"
BUILD = SOURCE / "build"
SOURCE_NAME = "firmware/stage2l_switch"
TEST_TABLE_SHA = "a52084ab8fcb04880b8454e11c8798725518d0997da122c049747b796a510343"
DAILY_TABLE_SHA = "44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05"
BANK_SHA = "9b04ab6b5fe30c2a59d2b88c3219ffca6220791e7f4c5ba1bbf11b4c2278cb38"
LABELS = (("fixed-stage2l-r2", False, False), ("fixed-stage2l-sanitizers-r2", True, False),
          ("daily-sweep-r2", False, True), ("daily-sweep-sanitizers-r2", True, True))
CASE_NAMES = {"first_rpc_failed", "first_reply_lost", "control_already_stock",
              "ownership_lost", "control_write_reply_lost", "success"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def evidence_keys(daily):
    files = {p for p in SOURCE.rglob("*") if p.is_file() and p.suffix in {".c", ".h", ".inc"}
             and "build" not in p.relative_to(SOURCE).parts}
    files.update({HERE / "reproduce.py", HERE / ("sweep.c" if daily else "reproduce.c")})
    return {str(p.relative_to(ROOT)) for p in files}


def validate_report(report, *, sanitizers, daily, expected_keys):
    assert report["evidence"] == "HOST_BEHAVIOR_ONLY" and report["source"] == SOURCE_NAME
    assert report["sanitizers"] is sanitizers, "host/sanitizer evidence mislabeled"
    assert report["table_sha256"] == (DAILY_TABLE_SHA if daily else TEST_TABLE_SHA)
    assert report["bank_sha256"] == BANK_SHA
    assert set(report["sources_sha256"]) == expected_keys, "incomplete or foreign source/driver identity"
    flags = report["compiler_args"]
    assert isinstance(flags, list) and flags[0] == "clang"
    assert all(flag in flags for flag in ("-DRECIPE_FW_HOST", "-DRFW_DEEP_ENABLED=1"))
    sanitizer_flags = {"-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"}
    assert (sanitizer_flags <= set(flags)) if sanitizers else not any(flag.startswith("-fsanitize") for flag in flags)
    assert len(report["executable_sha256"]) == 64
    names = {"daily_sweep"} if daily else CASE_NAMES
    cases = report["cases"]
    assert report["passed"] == report["total"] == len(cases) == len(names)
    assert {case["case"] for case in cases} == names
    assert all(case["check_passed"] is True for case in cases)
    for case in cases:
        if daily:
            assert case["ordered_pairs"] == 64 and case["sweep_steps"] == 6
            assert case["all_stock_rows_restored"] is True and case["reopened_slot"] == 4
        elif case["case"] == "success":
            assert case["return_status"] == 0 and case["applied_slot"] == case["highlighted_slot"] == 4
            assert case["deep_active"] == case["uncertain"] == 0 and case["t_control"] == 2
            assert case["all_stock_rows_restored"] is True and case["additional_previews"] == 1
        else:
            assert case["return_status"] == 11 and case["applied_slot"] == case["highlighted_slot"] == 6
            assert case["deep_active"] == 5 and case["additional_previews"] == 0
            assert case["settings_unchanged"] is True and case["failed_switch_not_published"] is True
            assert case["uncertain"] == int(case["case"] == "control_write_reply_lost")


def create_candidate():
    assert json.loads((BUILD / "manifest.json").read_text())["variant"] == "deep"
    assert sha((BUILD / "payload.bin").read_bytes()) == "5510f2be98906f3b17c8a664be6108a12def3a26c7b575e38812744b0de66c44"
    spec = importlib.util.spec_from_file_location("switch_image_audit", SOURCE / "tools/audit_image.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    files, hooks, payload, symbols = audit.read_inputs(BUILD)
    report = audit.audit(files, hooks, payload, symbols)
    original = files["ilaunch3"]
    body = bytearray(original)
    for hook in hooks["hooks"]:
        start = int(hook["file_offset"], 16)
        body[start:start + hook["length"]] = bytes.fromhex(hook["new_bytes"])
    body[0x796c:0x796c + len(payload)] = payload
    checksum = sum(value * (i % 6 + 2) for i, value in enumerate(body[512:])) & 0xffffffff
    struct.pack_into(">I", body, 0x16c, checksum)
    assert sha(body) == report["candidate_image_sha256"]
    trace = json.loads((ROOT / "research/stage1b_recovery/native-gates-update-trace.json").read_text())
    sections = [struct.unpack_from(">5I", original, 32 + i * 20) for i in range(16)]
    windows = []
    for group, count in (("boot_trace", 14), ("osd_trace", 16)):
        source = trace["prior_window_revalidation"][group]["windows"]
        assert len(source) == count
        for window in source:
            va, size = int(window["va"], 16), window["length"]
            offsets = [src + 512 + va - base for src, base, n, _, _ in sections
                       if base <= va and va + size <= base + n]
            assert len(offsets) == 1
            start = offsets[0]
            part = body[start:start + size]
            assert part == original[start:start + size] and sha(part) == window["expected_sha256"]
            windows.append(dict(group=group, name=window["name"], va=window["va"],
                                file_offset=hex(start), length=size, sha256=sha(part),
                                byte_identical=True))
    report.update(protected_update_windows=windows, protected_update_windows_count=len(windows),
                  variant="deep", camera_executed=False)
    return bytes(body), report


def main():
    volume = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert volume["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"]
    baseline = json.loads((HERE / "local/baseline-stage2j/results.json").read_text())
    assert baseline["total"] == 6 and baseline["passed"] == 2
    for label, sanitizers, daily in LABELS:
        evidence = json.loads((HERE / "local" / label / "results.json").read_text())
        validate_report(evidence, sanitizers=sanitizers, daily=daily, expected_keys=evidence_keys(daily))
        for name, digest in evidence["sources_sha256"].items():
            assert sha((ROOT / name).read_bytes()) == digest, f"stale independent evidence: {name}"
    assert "/ATA1/P" not in "\n".join(p.read_text() for p in SOURCE.glob("*.c"))
    image, audit = create_candidate()
    assert audit["protected_update_windows_count"] == 30
    assert sum(value * (i % 6 + 2) for i, value in enumerate(image[512:])) & 0xffffffff == struct.unpack_from(">I", image, 0x16c)[0]

    protected = json.loads((HERE / "local/protected-before.json").read_text())
    assert all(sha((ROOT / name).read_bytes()) == digest for name, digest in protected.items()), "protected baseline changed"
    test = (ROOT / "artifacts/stage2j-packages/tables-v5-fuji-test/DEEPTBL0.DAT").read_bytes()
    daily_dir = ROOT / "artifacts/stage2j-packages/tables-v5-fuji-daily"
    daily = (daily_dir / "DEEPTBL0.DAT").read_bytes()
    assert sha(test) == "a52084ab8fcb04880b8454e11c8798725518d0997da122c049747b796a510343"
    assert sha(daily) == "44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05"
    assert daily == (daily_dir / "DEEPTBL1.DAT").read_bytes()
    assert test[:12] == daily[:12] and test[16:16 + 6 * 448] == daily[16:16 + 6 * 448]
    assert daily[16 + 6 * 448 + 1] == daily[16 + 7 * 448 + 1] == 0

    previous = ROOT / "artifacts/stage2j-packages/stage2j"
    files = {p.name: p.read_bytes() for p in (previous / "candidate/SD_ROOT").iterdir() if p.is_file()}
    assert len(files) == 33
    assert sha(files["ilaunch3"]) == "f181b7a451b28caafe1ef62b93a9b5f64e18a61fbee49aa9ac50dbc305d2c60e"
    files["ilaunch3"] = image
    files.update({"DEEPTBL0.DAT": daily, "DEEPTBL1.DAT": daily})
    official = ROOT / "artifacts/firmware/gxr-1.51"
    recovery = {p.name: p.read_bytes() for p in (previous / "recovery-official-1.51/SD_ROOT").iterdir() if p.is_file()}
    assert len(recovery) == 29
    assert all(value == (official / name).read_bytes() for name, value in recovery.items())
    assert all(files[name] == value for name, value in recovery.items() if name != "ilaunch3")
    assert len(files) == 35 and "P" not in files

    packages = ROOT / "artifacts/stage2l-switch-packages"
    packages.mkdir(exist_ok=True)
    (packages / ".gitignore").write_text("*\n")
    package = packages / ("stage2l-switch-" + sha(image)[:12])
    assert not package.exists(), "refusing to replace an existing package"
    for directory, contents in (("candidate/SD_ROOT", files), ("recovery-official-1.51/SD_ROOT", recovery)):
        target = package / directory
        target.mkdir(parents=True)
        for name, data in contents.items():
            path = target / name
            path.write_bytes(data)
            assert path.read_bytes() == data
    evidence_dir = package / "evidence"
    evidence_dir.mkdir()
    for name in ("manifest.json", "verification.json", "hooks.json"):
        (evidence_dir / name).write_bytes((BUILD / name).read_bytes())
    audit.update(status="CANDIDATE_IMAGE_HOST_VERIFIED", upgrade_package_generated=True,
                 image_written=True, artifact_readback_verified=True,
                 artifact_path=str((package / "candidate/SD_ROOT/ilaunch3").relative_to(ROOT)))
    (evidence_dir / "candidate_verification.json").write_text(json.dumps(audit, indent=2) + "\n")
    for label in ("baseline-stage2j", *(item[0] for item in LABELS)):
        (evidence_dir / f"{label}.json").write_bytes((HERE / "local" / label / "results.json").read_bytes())
    for relative, name in (("r2/final-evidence.json", "build-r2-final-evidence.json"),
                           ("r2/reopen-after/results.json", "reopen-history.json"),
                           ("r2/independent-review/results.json", "r1-counterexample-now-fixed.json")):
        (evidence_dir / name).write_bytes((BUILD / relative).read_bytes())
    (evidence_dir / "worker-remedy-report.md").write_bytes((HERE / "WORKER_R2.md").read_bytes())
    manifest = {
        "status": "HOST_VERIFIED_CANDIDATE_CAMERA_NOT_RUN",
        "image_sha256": sha(image), "image_bytes": len(image),
        "payload_sha256": sha((BUILD / "payload.bin").read_bytes()),
        "table_sha256": sha(daily), "candidate_files": len(files), "official_recovery_files": len(recovery),
        "protected_baseline_files_unchanged": len(protected), "normal_update_windows_unchanged": 30,
        "slot08_external_loader": False, "table_slots01_to06_identical_to_installed_test": True,
        "table_slots07_and08": "Existing daily-set stock aliases; no calibration values were changed",
        "new_colour_accuracy_claim": False, "sd_accessed": False, "camera_executed": False,
        "R_all_restored_user_confirmed": True,
        "pre_update_requirement": "User has confirmed R-all RESTORED on the current P0 firmware. Do not ask for another restore. The new firmware does not run P helpers.",
        "reopen_history": "Retained only when the same occupied slot keeps the complete 49-byte recipe identity; uncertain remains sticky.",
        "recovery_limit": "Official files are verified; arbitrary bad-MAIN recovery is not established.",
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (package / "README.txt").write_text(
        "配方切换修复候选，电脑验证通过，尚未在相机运行。\n"
        "candidate/SD_ROOT：35个文件。只更新机身ilaunch3，模块固件仍为官方。\n"
        "用户已确认旧固件下R-all显示RESTORED，无需重复恢复；待独立复审通过再准备卡。\n"
        "新版不再加载P，07/08使用现有daily表的标准别名，01至06的颜色表保持原样。\n"
        "深层切换失败不再发布新选择；部分写入后失败继续锁住深层切换，不盲重试。\n"
        "同一cache重开仅在原槽49字节identity未变时保留历史回退位置，不代表ISP已恢复。\n"
        "上机仍需验证06到04的颜色恢复、扫过槽位后的退出，以及DNG与JPEG配对。\n"
        "recovery-official-1.51/SD_ROOT为29个官方恢复文件，不保证任意故障下可恢复。\n"
    )
    lines = [f"{sha(p.read_bytes())}  {p.relative_to(package)}" for p in sorted(package.rglob("*")) if p.is_file()]
    (package / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    assert len(list((package / "candidate/SD_ROOT").iterdir())) == 35
    for line in (package / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert sha((package / name).read_bytes()) == digest, f"package readback changed: {name}"
    print(json.dumps({"package": str(package.relative_to(ROOT)), **manifest}))


if __name__ == "__main__":
    main()
