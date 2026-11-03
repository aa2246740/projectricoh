#!/usr/bin/env python3
"""Read-only source/ELF inventory. Only this research directory is writable.

No target compilation, image emission, device access, network or polling.
Run with /usr/bin/python3 -I -B from the repository root.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
ELF = ROOT / "firmware/resident_v36/local/resident/build/resident.elf"
BODY = ROOT / "firmware/image_v36/local/body-v36/candidate/SD_ROOT/ilaunch3"
OFFICIAL = ROOT / "artifacts/firmware/gxr-1.51/ilaunch3"
PINS = {
    "firmware/resident_v36/local/resident/build/resident.elf": "5d66184ce33f280aa370ebfc1753fe74e8ad398f01558406909733cec779acff",
    "firmware/image_v36/local/body-v36/candidate/SD_ROOT/ilaunch3": "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008",
    "artifacts/firmware/gxr-1.51/ilaunch3": "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def audit(event, args):
    if event == "open":
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            writes = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            )
            if writes:
                assert Path(path).resolve().is_relative_to(HERE), ("write fence", path)
    if event.startswith("socket."):
        raise RuntimeError("network disabled")
    if event in ("os.remove", "os.rmdir", "os.mkdir", "os.rename", "os.symlink", "os.link",
                 "os.truncate", "os.chmod", "os.chown", "os.utime", "os.setxattr", "os.removexattr"):
        for path in args[:2] if event in ("os.rename", "os.symlink", "os.link") else args[:1]:
            if isinstance(path, (str, bytes, os.PathLike)):
                assert Path(path).resolve().is_relative_to(HERE), ("mutation fence", path)
    if event == "subprocess.Popen":
        argv = list(args[1])
        command = Path(args[0]).name
        allowed = (
            command == "diskutil" and argv[1:] == ["info", "-plist", "/Volumes/Workspace"]
        ) or (
            command == "git" and argv[1:] == ["check-ignore", "-q", str(LOCAL / "guard")]
            and Path(args[2]).resolve() == ROOT
        )
        assert allowed, ("process fence", argv)


sys.addaudithook(audit)


def preflight():
    assert ROOT == Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
    assert Path.cwd().resolve() == ROOT
    v = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert v.get("VolumeUUID") == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert v.get("MountPoint") == "/Volumes/Workspace" and v.get("FilesystemType") == "apfs"
    assert v.get("WritableVolume") and v.get("WritableMedia")
    assert subprocess.run(["git", "check-ignore", "-q", str(LOCAL / "guard")], cwd=ROOT).returncode == 0
    for p, expected in PINS.items():
        assert (ROOT / p).is_file(), p
        assert sha(ROOT / p) == expected, ("identity mismatch", p)
    LOCAL.mkdir(exist_ok=True)
    return {k: v[k] for k in ("VolumeUUID", "MountPoint", "FilesystemType", "WritableVolume")}


def write(name, value):
    assert re.fullmatch(r"[a-zA-Z0-9_.-]+", name)
    (LOCAL / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source_paths():
    paths = set(ROOT / p for p in PINS)
    for folder in ("firmware/resident_v36/resident", "firmware/resident_v36/engine_services"):
        paths.update(p for p in (ROOT / folder).iterdir() if p.is_file())
    dirs = (
        "firmware/resident_v36", "firmware/image_v36", "research/user_storage_r3",
        "research/g122_hint_design", "research/g123_fix", "research/review_g122",
        "research/g121_field_fix", "research/grain_raw_feasibility", "research/ui_v2_design",
        "research/r28_first_open_r1", "research/stage1b_recovery", "research/boot_hang_50mm",
        "firmware/stage2l_restore", "research/review_v36_body",
    )
    for folder in dirs:
        base = ROOT / folder
        if base.exists():
            paths.update(p for p in base.iterdir() if p.is_file() and p.suffix in (".md", ".py", ".json", ".ld", ".h", ".c", ".S"))
    for folder in ("firmware/resident_v36/local/resident/build",):
        paths.update(p for p in (ROOT / folder).iterdir() if p.is_file())
    for path in (
        "firmware/resident_v36/local/resident/linked_hooks.S",
        "firmware/resident_v36/local/resident/hooks.json",
        "firmware/resident_v36/local/resident/size.json",
        "firmware/resident_v36/local/resident/target-layout.json",
        "firmware/resident_v36/local/resident/trust.json",
        "firmware/resident_v36/local/resident/trust.c",
        "research/user_storage_r3/local/sections.json",
        "research/user_storage_r3/local/window-index.json",
        "research/user_storage_r3/local/resident-identity.json",
        "research/user_storage_r3/local/storage-task.asm.txt",
        "research/user_storage_r3/local/ui-event-main.asm.txt",
    ):
        paths.add(ROOT / path)
    return sorted(paths)


def snapshot():
    return {str(p.relative_to(ROOT)): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in source_paths()}


def parse_elf(path):
    data = path.read_bytes()
    assert data[:6] == b"\x7fELF\x01\x02", "expected ELF32 big-endian"
    eh = struct.unpack_from(">16sHHIIIIIHHHHHH", data)
    assert eh[2] == 88, ("expected M32R", eh[2])
    shoff, shentsize, shnum, shstrndx = eh[6], eh[11], eh[12], eh[13]
    assert shentsize == 40
    headers = [struct.unpack_from(">10I", data, shoff + i * 40) for i in range(shnum)]
    shstr = headers[shstrndx]
    names = data[shstr[4]:shstr[4] + shstr[5]]

    def string(blob, off):
        return blob[off:blob.index(0, off)].decode("ascii")

    sections = []
    for i, h in enumerate(headers):
        sections.append(dict(index=i, name=string(names, h[0]), type=h[1], flags=h[2], address=h[3],
                             offset=h[4], bytes=h[5], link=h[6], info=h[7], alignment=h[8], entsize=h[9]))
    symbols = []
    for sec in sections:
        if sec["type"] != 2:
            continue
        strings = sections[sec["link"]]
        st = data[strings["offset"]:strings["offset"] + strings["bytes"]]
        for off in range(sec["offset"], sec["offset"] + sec["bytes"], 16):
            name, value, size, info, other, shndx = struct.unpack_from(">IIIBBH", data, off)
            symbols.append(dict(name=string(st, name), address=value, bytes=size,
                                type=info & 15, binding=info >> 4, section=shndx))
    return data, sections, symbols


def inventory():
    data, secs, syms = parse_elf(ELF)
    symbols = {s["name"]: s for s in syms if s["name"]}
    payload = next(s for s in secs if s["name"] == ".payload")
    raw = data[payload["offset"]:payload["offset"] + payload["bytes"]]
    mapping = json.loads((ROOT / "research/user_storage_r3/local/sections.json").read_text())
    start = payload["address"]
    sec = next(s for s in mapping if s["vma"] <= start and start + len(raw) <= s["vma"] + s["size"])
    off = sec["file"] + start - sec["vma"]
    body = BODY.read_bytes()
    assert body[off:off + len(raw)] == raw
    end = symbols["__resident_code_end"]["address"]
    assert end == start + len(raw) == 0x20054638
    map_text = (ELF.parent / "resident.map").read_text()
    content = map_text.split(".payload ", 1)[1].split(".root ", 1)[0]
    rows = []
    for addr, length, obj in re.findall(r"^\s+(?:\.\S+\s+)?(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+\S*/([^/\s]+\.o)\s*$", content, re.M):
        lo, n = int(addr, 16), int(length, 16)
        if n and start <= lo and lo + n <= end:
            rows.append(dict(address=lo, bytes=n, object=obj))
    covered = {}
    for r in rows:
        for a in range(r["address"], r["address"] + r["bytes"]):
            assert a not in covered, ("overlapping map section", hex(a))
            covered[a] = r["object"]
    objects = {}
    for obj in covered.values():
        objects[obj] = objects.get(obj, 0) + 1
    funcs = []
    for s in syms:
        if s["type"] == 2 and s["bytes"] and start <= s["address"] < end:
            owners = {covered.get(a, "linker") for a in range(s["address"], s["address"] + s["bytes"])}
            assert len(owners) == 1, (s, owners)
            funcs.append({**s, "object": next(iter(owners))})
    for s in syms:
        if s["bytes"] and s["type"] == 1 and start <= s["address"] < end:
            funcs.append({**s, "object": covered.get(s["address"], "linker")})
    report = dict(elf=str(ELF.relative_to(ROOT)), elf_sha256=sha(ELF), body_sha256=sha(BODY),
                  payload_address=hex(start), payload_file_offset=hex(off), payload_bytes=len(raw),
                  payload_sha256=hashlib.sha256(raw).hexdigest(), payload_matches_body=True,
                  code_end=hex(end), window_bytes=0x20054800-start, root_bytes=256,
                  physical_gap=0x20054700-end, mandatory_reserve=200, additional_bytes=0,
                  linked_objects=objects, linker_padding=len(raw)-len(covered),
                  function_bytes=sum(s["bytes"] for s in funcs if s["type"] == 2),
                  data_symbol_bytes=sum(s["bytes"] for s in funcs if s["type"] == 1))
    assert sum(objects.values()) + report["linker_padding"] == len(raw)
    write("resident-inventory.json", report)
    write("resident-symbols.json", sorted(funcs, key=lambda s: s["address"]))
    write("resident-sections.json", secs)
    write("resident-map-input-sections.json", rows)
    (HERE / "resident-symbols.tsv").write_text("object\tsymbol\taddress\tbytes\ttype\n" + "".join(
        f'{s["object"]}\t{s["name"]}\t{s["address"]:#010x}\t{s["bytes"]}\t{s["type"]}\n'
        for s in sorted(funcs, key=lambda s: (s["object"], s["address"]))))
    print(json.dumps(report, ensure_ascii=False, indent=2))


def anchors():
    official, body = OFFICIAL.read_bytes(), BODY.read_bytes()
    mapping = json.loads((ROOT / "research/user_storage_r3/local/sections.json").read_text())
    specs = json.loads((HERE / "hook-catalog.json").read_text())
    found, raw_records = [], []
    for h in specs:
        if h["address"] is None:
            found.append(dict(id=h["id"], status="UNRESOLVED_ADDRESS", address=None))
            continue
        address = int(h["address"], 16)
        section = next(s for s in mapping if s["vma"] <= address < s["vma"] + s["size"])
        offset = section["file"] + address - section["vma"]
        start, count = max(address - 8, section["vma"]), 48
        file_start = section["file"] + start - section["vma"]
        text = ROOT / f'research/irom_storage/local/section{section["index"]:02d}.asm.txt'
        lines = []
        at_instruction = False
        for line in text.read_text().splitlines():
            m = re.match(r"\s*([0-9a-f]{8}):\s*((?:[0-9a-f]{2} ){1,7}[0-9a-f]{2})(?:\s|\t)", line)
            if m and start <= int(m[1], 16) < start + count:
                va = int(m[1], 16)
                b = bytes.fromhex(m[2])
                off = section["file"] + va - section["vma"]
                assert official[off:off+len(b)] == b, (text, line)
                lines.append(line)
                at_instruction |= va == address
        assert lines and at_instruction, ("address is not a decoded instruction start", h["id"], hex(address))
        o = official[file_start:file_start+count]
        b = body[file_start:file_start+count]
        found.append(dict(id=h["id"], address=hex(address), file_offset=hex(offset),
                          status="STATIC_INSTRUCTION_BOUNDARY_ONLY", window_start=hex(start), window_bytes=len(o),
                          official_sha256=hashlib.sha256(o).hexdigest(), body_sha256=hashlib.sha256(b).hexdigest(),
                          equal_window=o == b, section=section["index"],
                          full_hook_contract_proven=False))
        raw_records.append(dict(id=h["id"], address=hex(address), start=hex(start),
                                official_hex=o.hex(), body_hex=b.hex(), disassembly=lines,
                                source=str(text.relative_to(ROOT))))
    write("anchor-bytes.json", raw_records)
    (HERE / "hook-anchors.json").write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n")
    print("Static anchors", sum(h["address"] is not None for h in specs), "located; unresolved",
          sum(h["address"] is None for h in specs), "; no patch site approved")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("action", choices=("before", "after", "inventory", "extend", "anchors"))
    args = a.parse_args()
    volume = preflight()
    if args.action == "before":
        assert not (LOCAL / "inputs-before.json").exists(), "baseline already exists"
        write("volume.json", volume)
        write("inputs-before.json", snapshot())
        write("run.json", dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                               scope=str(HERE.relative_to(ROOT)), network=False, device=False,
                               product_build=False, subagents=False))
        print("Frozen", len(snapshot()), "input files")
    elif args.action == "extend":
        before = json.loads((LOCAL / "inputs-before.json").read_text())
        extras = json.loads((LOCAL / "inputs-extra.json").read_text()) if (LOCAL / "inputs-extra.json").exists() else {}
        for p in json.loads((HERE / "extra-inputs.json").read_text()):
            assert not (ROOT / p).resolve().is_relative_to(HERE)
            current = {"bytes": (ROOT / p).stat().st_size, "sha256": sha(ROOT / p)}
            if p in before:
                assert before[p] == current, ("baseline drift", p)
                continue
            assert p not in extras or extras[p] == current
            extras[p] = current
        write("inputs-extra.json", extras)
        print("Supplemental frozen inputs", len(extras))
    elif args.action == "after":
        before = json.loads((LOCAL / "inputs-before.json").read_text())
        extra = json.loads((LOCAL / "inputs-extra.json").read_text()) if (LOCAL / "inputs-extra.json").exists() else {}
        expected = {**before, **extra}
        after = {p: {"bytes": (ROOT/p).stat().st_size, "sha256": sha(ROOT/p)} for p in expected}
        changed = [p for p in expected if expected[p] != after[p]]
        write("inputs-after.json", after)
        write("input-integrity.json", dict(status="PASS" if not changed else "FAIL", files=len(expected), changed=changed))
        print("Integrity", len(expected), "files; changed", len(changed))
        assert not changed, changed
    elif args.action == "inventory":
        inventory()
    else:
        anchors()


if __name__ == "__main__":
    main()
