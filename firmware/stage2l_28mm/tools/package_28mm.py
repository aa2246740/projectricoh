#!/usr/bin/env python3
"""Stage the qlaunch card directory. Never writes a camera card or outside this tree."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zipfile

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
PACKAGE = LOCAL / "package"
SD = PACKAGE / "SD_ROOT"
ZIP = ROOT / "artifacts/downloads/gxr-151.zip"
PREFIX = "GXR Update/Firmware rel 1.51/"


def sha(data):
    if isinstance(data, Path):
        h = hashlib.sha256()
        with data.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    return hashlib.sha256(data).hexdigest()


def main():
    protected = json.loads((LOCAL / "protected-before.json").read_text())
    if not all(sha(ROOT / name) == digest for name, digest in protected.items()):
        raise SystemExit("a frozen input changed")
    comparison = json.loads((LOCAL / "object-comparison.json").read_text())
    if not (comparison["logical_control_flow_unchanged"] and comparison["nine_hooks_byte_identical"]
            and comparison["status"] == "NORMALIZED_DISASSEMBLY_EQUIVALENT"):
        raise SystemExit("equivalence result is not in place")
    evidence = json.loads((LOCAL / "build/verification.json").read_text())
    manifest = json.loads((LOCAL / "build/manifest.json").read_text())
    evidence["inputs_sha256"] = manifest["build_inputs_sha256"]
    (LOCAL / "build/verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")

    spec = importlib.util.spec_from_file_location("qlaunch_audit", HERE / "tools/audit_image.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    files, hooks, payload, symbols = audit.read_inputs(LOCAL / "build")
    report = audit.audit(files, hooks, payload, symbols)
    if len(payload) != 8084 or sha(payload) != comparison["qlaunch_payload_sha256"]:
        raise SystemExit("audited payload is not the compared payload")
    original = files["ilaunch3"]
    candidate = bytearray(original)
    for hook in hooks["hooks"]:
        pos, size = int(hook["file_offset"], 16), hook["length"]
        candidate[pos:pos + size] = bytes.fromhex(hook["new_bytes"])
    candidate[0x796C:0x796C + len(payload)] = payload
    checksum = sum(value * (i % 6 + 2) for i, value in enumerate(candidate[512:])) & 0xFFFFFFFF
    struct.pack_into(">I", candidate, 0x16C, checksum)
    candidate = bytes(candidate)
    if sha(candidate) != report["candidate_image_sha256"] or len(candidate) != 3993340:
        raise SystemExit("reconstructed ilaunch3 disagrees with the in-memory audit")
    if candidate[0x9900:0x9A00] != b"\xff" * 256:
        raise SystemExit("probe reserve is not intact")

    baseline = (ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/ilaunch3").read_bytes()
    changed = [i for i, (a, b) in enumerate(zip(baseline, candidate)) if a != b]
    if len(baseline) != len(candidate):
        raise SystemExit("image length differs from the daily Stage2l body")
    if any(not (0x16C <= i < 0x170 or 0x796C <= i < 0x9900) for i in changed):
        raise SystemExit("ilaunch3 differs from Stage2l outside the payload and the container checksum")
    with (LOCAL / "byte-diff-image.tsv").open("w") as log:
        log.write("file_offset\tstage2l\tqlaunch\tregion\n")
        for pos in changed:
            region = "container_checksum" if pos < 512 else "payload"
            log.write(f"0x{pos:08x}\t{baseline[pos]:02x}\t{candidate[pos]:02x}\t{region}\n")

    trace = json.loads((ROOT / "research/stage1b_recovery/native-gates-update-trace.json").read_text())
    sections = [struct.unpack_from(">5I", original, 32 + i * 20) for i in range(16)]
    windows = []
    for group, count in (("boot_trace", 14), ("osd_trace", 16)):
        source = trace["prior_window_revalidation"][group]["windows"]
        if len(source) != count:
            raise SystemExit(f"{group} window count changed")
        for window in source:
            va, size = int(window["va"], 16), window["length"]
            hits = [src + 512 + va - base for src, base, n, _, _ in sections if base <= va and va + size <= base + n]
            if len(hits) != 1:
                raise SystemExit(f"update window {window['name']} is not in one section")
            pos = hits[0]
            part = candidate[pos:pos + size]
            if part != original[pos:pos + size] or sha(part) != window["expected_sha256"]:
                raise SystemExit(f"update window {window['name']} changed")
            windows.append(window["name"])
    if len(windows) != 30:
        raise SystemExit("expected 30 boot/OSD windows")

    official = {}
    with zipfile.ZipFile(ZIP) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        if len(names) != 29:
            raise SystemExit(f"zip has {len(names)} files, expected 29")
        for name in names:
            base = name.split("/")[-1]
            data = archive.read(name)
            disk = ROOT / "artifacts/firmware/gxr-1.51" / base
            if not disk.is_file() or disk.read_bytes() != data:
                raise SystemExit(f"{base} in the zip is not the extracted official file")
            if base != "ilaunch3":
                official[base] = data
    if len(official) != 28:
        raise SystemExit("expected 28 official unit files besides ilaunch3")
    table = (LOCAL / "DEEPTBL_28mm.DAT").read_bytes()
    if len(table) != 3600:
        raise SystemExit("DEEPTBL length")

    if SD.exists():
        for path in SD.iterdir():
            path.unlink()
    else:
        SD.mkdir(parents=True)
    staged = dict(official)
    staged["ilaunch3"] = candidate
    staged["DEEPTBL0.DAT"] = table
    staged["DEEPTBL1.DAT"] = table
    for name, data in staged.items():
        path = SD / name
        path.write_bytes(data)
        if path.read_bytes() != data:
            raise SystemExit(f"readback failed for {name}")
    if staged["ilaunch3"][0x796C:0x796C + len(payload)] != payload:
        raise SystemExit("staged payload window mismatch")
    entries = sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    sums = PACKAGE / "SHA256SUMS"
    sums.write_text("".join(f"{sha(p.read_bytes())}  {p.relative_to(PACKAGE)}\n" for p in entries))
    for line in sums.read_text().splitlines():
        digest, name = line.split("  ", 1)
        if sha(PACKAGE / name) != digest:
            raise SystemExit(f"checksum reread failed: {name}")
    summary = {
        "ilaunch3_sha256": sha(candidate), "ilaunch3_bytes": len(candidate),
        "payload_sha256": sha(payload), "payload_bytes": len(payload),
        "deeptbl_sha256": sha(table), "deeptbl_bytes": len(table),
        "official_unit_files": 28, "sd_root_files": len(staged),
        "difference_from_stage2l_bytes": len(changed),
        "difference_only_payload_and_checksum": True,
        "protected_update_windows": 30, "checksum": f"{checksum:08x}",
        "camera_executed": False, "sd_accessed": False,
    }
    (LOCAL / "package-readback.json").write_text(json.dumps(summary, indent=2) + "\n")
    (LOCAL / "build/candidate_verification.json").write_text(json.dumps(report, indent=2) + "\n")
    if not all(sha(ROOT / name) == digest for name, digest in protected.items()):
        raise SystemExit("a frozen input changed while packaging")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
