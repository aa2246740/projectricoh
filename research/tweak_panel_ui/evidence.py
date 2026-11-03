#!/usr/bin/env python3
"""Read-only GNU M32R evidence queries; all extracted material stays in local/."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
FW = ROOT / "artifacts/firmware/gxr-1.51/ilaunch3"
DIS = ROOT / "research/tooling_m32r/disasm"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"


def preflight():
    info = plistlib.loads(subprocess.check_output(
        ["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert info["MountPoint"] == "/Volumes/Workspace"
    assert info["VolumeUUID"].upper() == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert info["FilesystemType"] == "apfs"
    assert info.get("WritableVolume") is True
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / "volume.json").write_text(json.dumps(info, indent=2, default=str) + "\n")


def save(name, data):
    assert re.fullmatch(r"[a-zA-Z0-9_.-]+", name)
    (LOCAL / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def sections(data):
    return [(i, s + 512, v, n) for i, (s, v, n, _, _) in enumerate(
        struct.unpack_from(">IIIII", data, 32 + i * 20) for i in range(16))]


def offset(secs, va, count=1):
    return next(s + va - v for _, s, v, n in secs if v <= va and va + count <= v + n)


def dump(data, secs, label, lo, hi):
    rows = []
    sources = set()
    for i, _, v, n in secs:
        if lo >= v + n or hi <= v:
            continue
        path = next(DIS.glob(f"ilaunch3-sec{i:02d}-*.disasm.txt"))
        sources.add(str(path.relative_to(ROOT)))
        for no, line in enumerate(path.read_text().splitlines(), 1):
            m = re.match(r"^([0-9a-f]+):\s+([0-9a-f ]+)\t(.+)$", line)
            if m and lo <= int(m[1], 16) < hi:
                va = int(m[1], 16)
                raw = bytes.fromhex(m[2])
                assert data[offset(secs, va, len(raw)):offset(secs, va, len(raw))+len(raw)] == raw
                rows.append(f"{path.name}:{no} | {line}")
    assert rows, "No instructions in requested range"
    assert re.fullmatch(r"[a-zA-Z0-9_-]+", label)
    text = (f"# ilaunch3 [{lo:#x}, {hi:#x}); file offset {offset(secs, lo):#x}\n"
            "# GNU M32R source filename:line | original instruction, bytes checked.\n")
    (LOCAL / f"{label}.disasm.txt").write_text(text + "\n".join(rows) + "\n")
    print(f"{label}: {len(rows)} checked instruction rows")


def fresh(data, secs, label, lo, hi):
    assert re.fullmatch(r"[a-zA-Z0-9_-]+", label)
    part = LOCAL / f"{label}.bin"
    part.write_bytes(data[offset(secs, lo, hi-lo):offset(secs, lo, hi-lo)+hi-lo])
    command = [str(OBJDUMP), "-D", "-b", "binary", "-m", "m32r", "-EB",
               f"--adjust-vma={lo}", str(part)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    (LOCAL / f"{label}.fresh.disasm.txt").write_text(result.stdout)
    save(f"{label}.command.json", command)
    print(f"{label}: freshly disassembled {hi-lo} bytes")


def verify(data, secs):
    count = 0
    fresh_count = 0
    source_cache = {}
    for path in sorted(LOCAL.glob("*.disasm.txt")):
        for line in path.read_text().splitlines():
            m = re.match(r"([^:]+):(\d+) \| ([0-9a-f]+):\s+([0-9a-f ]+)\t(.+)$", line)
            if not m:
                continue
            source, number, address, raw, _ = m.groups()
            if source not in source_cache:
                source_cache[source] = (DIS / source).read_text().splitlines()
            original = line.split(" | ", 1)[1]
            assert source_cache[source][int(number)-1] == original
            va = int(address, 16)
            raw = bytes.fromhex(raw)
            at = offset(secs, va, len(raw))
            assert data[at:at+len(raw)] == raw
            count += 1
        if path.name.endswith(".fresh.disasm.txt"):
            for line in path.read_text().splitlines():
                m = re.match(r"\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+[0-9a-f]{2})\s+", line)
                if m:
                    va, raw = int(m[1], 16), bytes.fromhex(m[2])
                    at = offset(secs, va, len(raw))
                    assert data[at:at+len(raw)] == raw
                    fresh_count += 1
    hooks_path = LOCAL / "hook_candidates.json"
    hooks = json.loads(hooks_path.read_text()) if hooks_path.exists() else []
    for h in hooks:
        va, raw = int(h["va"], 16), bytes.fromhex(h["original_bytes"])
        at = offset(secs, va, len(raw))
        assert at == int(h["file_offset"], 16)
        assert data[at:at+len(raw)] == raw
    manifest = json.loads((ROOT / "firmware/stage2l_switch/hooks.json").read_text())
    assert hashlib.sha256(data).hexdigest() == manifest["image_sha256"]
    for h in manifest["hooks"]:
        at = int(h["file_offset"], 16)
        assert data[at:at+h["length"]] == bytes.fromhex(h["original_bytes"])
    result = {"firmware_sha256": hashlib.sha256(data).hexdigest(),
              "verified_excerpt_rows": count, "verified_hook_candidates": len(hooks),
              "verified_fresh_disassembly_rows": fresh_count,
              "verified_existing_hooks": len(manifest["hooks"]),
              "objdump_version": subprocess.check_output(
                  [str(OBJDUMP), "--version"], text=True).splitlines()[0],
              "camera_tested": False, "built": False}
    save("verification.json", result)
    print(json.dumps(result, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["dump", "fresh", "table", "verify"])
    p.add_argument("label", nargs="?")
    p.add_argument("start", nargs="?", type=lambda s: int(s, 0))
    p.add_argument("end_or_length", nargs="?", type=lambda s: int(s, 0))
    args = p.parse_args()
    preflight()
    data = FW.read_bytes()
    secs = sections(data)
    if args.action == "verify":
        verify(data, secs)
    elif args.action == "table":
        at = offset(secs, args.start, args.end_or_length)
        raw = data[at:at+args.end_or_length]
        save(args.label + ".json", {"va": hex(args.start), "file_offset": hex(at),
             "length": len(raw), "raw_hex": raw.hex(" ")})
        print(f"{args.label}: {len(raw)} data bytes retained in local/")
    else:
        {"dump": dump, "fresh": fresh}[args.action](
            data, secs, args.label, args.start, args.end_or_length)


if __name__ == "__main__":
    main()
