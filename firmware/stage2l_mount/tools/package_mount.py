#!/usr/bin/env python3
"""Create and read back a quarantined local package; never prepare real media."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import struct
import subprocess

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
PACKAGE = LOCAL / "package"
REFERENCE = ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8"
WARNING = "未审查，不得上卡"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_audit():
    spec = importlib.util.spec_from_file_location("mount_image_audit", HERE / "tools/audit_image.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    volume = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert volume["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert volume["FilesystemType"] == "apfs" and volume["WritableVolume"] and volume["WritableMedia"]
    reference_names = set()
    for line in (REFERENCE / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = (REFERENCE / name).resolve()
        assert path.is_relative_to(REFERENCE) and name not in reference_names
        assert sha(path.read_bytes()) == digest, name
        reference_names.add(name)
    assert reference_names == {str(p.relative_to(REFERENCE)) for p in REFERENCE.rglob("*") if p.is_file() and p.name != "SHA256SUMS"}
    comparison = json.loads((LOCAL / "object-comparison.json").read_text())
    assert comparison["logical_control_flow_unchanged"] and comparison["nine_hooks_byte_identical"]
    audit = load_audit()
    files, hooks, payload, symbols = audit.read_inputs(LOCAL / "build")
    report = audit.audit(files, hooks, payload, symbols)
    assert len(files) == 29 and len(payload) == comparison["mount_payload_bytes"]
    assert sha(payload) == comparison["mount_payload_sha256"]
    original = files["ilaunch3"]
    candidate = bytearray(original)
    for hook in hooks["hooks"]:
        pos, size = int(hook["file_offset"], 16), hook["length"]
        candidate[pos:pos+size] = bytes.fromhex(hook["new_bytes"])
    candidate[0x796c:0x796c+len(payload)] = payload
    checksum = sum(value * (i % 6 + 2) for i,value in enumerate(candidate[512:])) & 0xffffffff
    struct.pack_into(">I", candidate, 0x16c, checksum)
    assert sha(candidate) == report["candidate_image_sha256"]
    old = (REFERENCE / "candidate/SD_ROOT/ilaunch3").read_bytes()
    assert sha(old) == "efe6587190e845b1c28364c02a6b8bde14e046e7c7411393a4c9892124b6bfd7"
    changed = [i for i,(a,b) in enumerate(zip(old,candidate)) if a != b]
    assert len(old) == len(candidate)
    assert all(0x16c <= i < 0x170 or 0x796c <= i < 0x9900 for i in changed)
    with (LOCAL / "byte-diff-image.tsv").open("w") as log:
        log.write("file_offset\tstage2l\tmount\tregion\n")
        for pos in changed:
            region = "container_checksum" if pos < 512 else "payload_constant_or_widening_relocation"
            log.write(f"0x{pos:08x}\t{old[pos]:02x}\t{candidate[pos]:02x}\t{region}\n")
    trace = json.loads((ROOT / "research/stage1b_recovery/native-gates-update-trace.json").read_text())
    sections = [struct.unpack_from(">5I", original, 32+i*20) for i in range(16)]
    windows = []
    for group,count in (("boot_trace",14),("osd_trace",16)):
        source = trace["prior_window_revalidation"][group]["windows"]
        assert len(source) == count
        for window in source:
            va,size = int(window["va"],16),window["length"]
            hits = [src+512+va-base for src,base,n,_,_ in sections if base <= va and va+size <= base+n]
            assert len(hits) == 1
            pos = hits[0]
            part = candidate[pos:pos+size]
            assert part == original[pos:pos+size] and sha(part) == window["expected_sha256"]
            windows.append(dict(group=group,name=window["name"],file_offset=hex(pos),length=size,sha256=sha(part)))
    assert len(windows) == 30
    candidate_files = dict(files, ilaunch3=bytes(candidate))
    runtime = {name:(REFERENCE / "candidate/SD_ROOT" / name).read_bytes()
               for name in ("DEEPISP0.DAT","DEEPISP1.DAT","RECIPE20.DAT","RECIPE21.DAT")}
    table = (LOCAL / "DEEPTBL_mount_provisional.DAT").read_bytes()
    v6 = (ROOT / "research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL").read_bytes()
    leica = (ROOT / "research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT").read_bytes()
    fuji = (ROOT / "artifacts/stage2j-packages/tables-v5-fuji-test/DEEPTBL0.DAT").read_bytes()
    entry = lambda data,i: data[16+i*448:16+(i+1)*448]
    copy_proof = []
    for i,slot in ((1,1),(2,2),(3,3),(4,5),(6,7),(7,8)):
        source = v6 if i < 5 else leica
        assert entry(table,i) == entry(source,i)
        copy_proof.append(dict(slot=slot,whole_448_byte_entry_identical=True,
                               source="v6" if i < 5 else "Leica",sha256=sha(entry(table,i))))
    current,source = entry(table,5),entry(fuji,7)
    assert current[1:4] == source[1:4] and current[8:] == source[8:]
    assert current[0] == 6 and current[1] == 1 and current[445:447] == b"\0\2"
    copy_proof.append(dict(slot=6,source="Fuji round5 test slot08 = 06(a)",
                           all_bytes_identical_except_slot_and_default_identity_crc=True,
                           sha256=sha(current)))
    write_json(LOCAL / "provisional-entry-copy-proof.json",copy_proof)
    runtime["DEEPTBL0.DAT"] = runtime["DEEPTBL1.DAT"] = table
    for directory, contents in (("candidate/SD_ROOT",candidate_files),
                                ("runtime-data/SD_ROOT",runtime),
                                ("recovery-official-1.51/SD_ROOT",files)):
        target = PACKAGE / directory
        target.mkdir(parents=True,exist_ok=True)
        assert {p.name for p in target.iterdir()} <= set(contents), "unexpected existing package content"
        for name,data in contents.items():
            path = target / name
            path.write_bytes(data)
            assert path.read_bytes() == data
    readback = (PACKAGE / "candidate/SD_ROOT/ilaunch3").read_bytes()
    assert readback == candidate and readback[0x796c:0x796c+len(payload)] == payload
    assert len(list((PACKAGE / "candidate/SD_ROOT").iterdir())) == 29
    for name,data in files.items():
        assert (PACKAGE / "recovery-official-1.51/SD_ROOT" / name).read_bytes() == data
        if name != "ilaunch3":
            assert (PACKAGE / "candidate/SD_ROOT" / name).read_bytes() == data
    report.update(status="PACKAGED_ARTIFACT_READBACK_PASS_NOT_RELEASED", image_written=True,
                  artifact_readback_verified=True, upgrade_package_generated=True,
                  artifact_path=str((PACKAGE / "candidate/SD_ROOT/ilaunch3").relative_to(ROOT)),
                  protected_update_windows=windows, protected_update_windows_count=30,
                  baseline_image_sha256=sha(old), baseline_image_different_bytes=len(changed),
                  difference_only_payload_and_checksum=True, literal_constants_only_byte_difference=False,
                  camera_executed=False, sd_accessed=False, release_approved=False)
    evidence = PACKAGE / "evidence"
    evidence.mkdir(exist_ok=True)
    write_json(evidence / "candidate_verification.json",report)
    for name in ("manifest.json","verification.json","hooks.json","host-results.txt","sanitizers-results.txt",
                 "abi-tests.json","validator-host-accepted.txt","validator-sanitizers-accepted.txt"):
        (evidence / name).write_bytes((LOCAL / "build" / name).read_bytes())
    for name in ("object-comparison.json","address-evidence.json","provisional.json","provisional-entry-copy-proof.json","byte-diff-image.tsv"):
        (evidence / name).write_bytes((LOCAL / name).read_bytes())
    manifest = dict(status="BLOCKED_BY_ACCEPTANCE_CRITERIA", warning=WARNING,
                    image_sha256=sha(readback), image_bytes=len(readback),
                    payload_sha256=sha(payload), payload_bytes=len(payload),
                    table_sha256=sha(table), table_bytes=len(table),
                    firmware_files=29, unchanged_official_components=28,
                    runtime_data_files=6, official_recovery_files=29,
                    reference_package_files_verified=len(reference_names),
                    protected_update_windows=30, host_cases=283, sanitizer_cases=283,
                    strict_size_gate=False, literal_constants_only_image_byte_gate=False,
                    logical_control_flow_unchanged=True, release_approved=False,
                    camera_executed=False, sd_accessed=False)
    write_json(PACKAGE / "manifest.json",manifest)
    (PACKAGE / "NOTICE.txt").write_text(WARNING + "\npayload 比 Stage2l 多 4 B，任务大小条件未通过。\n")
    (PACKAGE / "README.txt").write_text(WARNING + "\n"
        "candidate/SD_ROOT 只含 29 个固件文件，28 个与官方逐字节一致，只有 ilaunch3 改动。\n"
        "runtime-data/SD_ROOT 为单独的 6 个配方数据文件，不计入这 29 个固件文件。\n"
        "recovery-official-1.51/SD_ROOT 为 29 个官方文件。恢复仍依赖相机能进入更新流程。\n"
        "8084 B payload 已用完普通保留区，严格大小门槛和纯常量字节门槛未过；禁止据本地主机通过直接写卡。\n"
        "当前两张卡的操作草案见 ../../REPORT.md，未执行相机或卡操作。\n")
    entries = sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p != PACKAGE / "SHA256SUMS")
    (PACKAGE / "SHA256SUMS").write_text("".join(f"{sha(p.read_bytes())}  {p.relative_to(PACKAGE)}\n" for p in entries))
    for line in (PACKAGE / "SHA256SUMS").read_text().splitlines():
        digest,name = line.split("  ",1)
        assert sha((PACKAGE / name).read_bytes()) == digest
    manifest["package_checksums_verified"] = len(entries)
    write_json(LOCAL / "package-readback.json",manifest)
    print(json.dumps(manifest,ensure_ascii=False))


if __name__ == "__main__":
    main()
