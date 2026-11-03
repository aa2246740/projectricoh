#!/usr/bin/env python3
"""Offline review evidence. Every write is confined to this directory."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "local"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
INPUTS = {
    "artifacts/firmware/gxr-1.51/ilaunch3": "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
    "firmware/image_v36/local/package/SD_ROOT/ilaunch3": "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008",
}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()

def save(name, value):
    assert re.fullmatch(r"[a-zA-Z0-9_.-]+", name)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def preflight():
    assert sys.flags.isolated and sys.flags.dont_write_bytecode
    v = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert v["MountPoint"] == "/Volumes/Workspace" and v["FilesystemType"] == "apfs"
    assert v["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and v["WritableVolume"]
    assert subprocess.run(["git", "check-ignore", "-q", str(OUT / "guard")], cwd=ROOT).returncode == 0
    OUT.mkdir(exist_ok=True)
    for rel, digest in INPUTS.items():
        assert sha(ROOT / rel) == digest, rel
    return {k: v[k] for k in ("MountPoint", "FilesystemType", "VolumeUUID", "WritableVolume")}

class Image:
    def __init__(self):
        self.data, self.body = [(ROOT / rel).read_bytes() for rel in INPUTS]
        self.sections = []
        for i in range(16):
            src, va, size, bss, bn = struct.unpack_from(">5I", self.data, 32 + 20 * i)
            assert src + 512 + size <= len(self.data)
            self.sections.append(dict(index=i, file=src + 512, vma=va, size=size, bss=bss, bss_size=bn))

    def off(self, va, n=1):
        hits = [s["file"] + va - s["vma"] for s in self.sections
                if s["vma"] <= va and va + n <= s["vma"] + s["size"]]
        assert len(hits) == 1, (hex(va), n)
        return hits[0]

    def raw(self, va, n):
        off = self.off(va, n)
        return self.data[off:off+n]

    def dump(self, lo, hi, label):
        assert re.fullmatch(r"[a-zA-Z0-9_.-]+", label)
        raw, off = self.raw(lo, hi-lo), self.off(lo, hi-lo)
        body = self.body[off:off+len(raw)]
        row = dict(label=label, start=hex(lo), end=hex(hi), file=hex(off), bytes=len(raw),
                   sha256=hashlib.sha256(raw).hexdigest(), official_equals_body=body == raw)
        for suffix, data in (("", raw), (".body", body)) if body != raw else (("", raw),):
            binary = OUT / (label + suffix + ".bin")
            binary.write_bytes(data)
            asm = subprocess.check_output([str(OBJDUMP), "-D", "-b", "binary", "-m", "m32r", "-EB",
                                           "--adjust-vma=" + hex(lo), str(binary)], text=True)
            (OUT / (label + suffix + ".asm.txt")).write_text(asm)
        if body != raw:
            row["differences"] = [dict(vma=hex(lo+i), official=x, body=y)
                                  for i, (x, y) in enumerate(zip(raw, body)) if x != y]
        return row

def protected_paths():
    paths = {ROOT / x for x in INPUTS} | {OBJDUMP}
    for rel in ("research/body_v4_storage/grok", "research/body_v4_storage/gpt",
                "research/body_v4_storage/gemini", "research/user_storage_r1", "research/user_storage_r2",
                "research/user_storage_r3", "firmware/resident_v36/resident"):
        paths.update(p for p in (ROOT / rel).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for rel in ("research/body_v4_storage/SYNTHESIS.md", "research/review_g123/REVIEW.md",
                "docs/RESEARCH_PROTOCOL.md", "firmware/resident_v36/local/resident/size.json",
                "firmware/resident_v36/local/resident/hooks.json"):
        paths.add(ROOT / rel)
    return sorted(paths)

def init():
    assert not (OUT / "protected-before.json").exists()
    before = {str(p.relative_to(ROOT)): dict(sha256=sha(p), bytes=p.stat().st_size)
              for p in protected_paths()}
    save("protected-before.json", before)
    rows = []
    for rel in ("research/body_v4_storage/grok", "research/body_v4_storage/gpt", "research/body_v4_storage/gemini",
                "research/user_storage_r1", "research/user_storage_r2", "research/user_storage_r3"):
        manifest = ROOT / rel / "SHA256SUMS"
        entries = []
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            digest, target = line.split(maxsplit=1)
            target = target.lstrip("*")
            p = ROOT / target
            assert p.resolve().is_relative_to((ROOT / rel).resolve()), target
            entries.append(dict(path=target, matches=p.is_file() and sha(p) == digest))
        rows.append(dict(manifest=str(manifest.relative_to(ROOT)), count=len(entries),
                         status="PASS" if all(x["matches"] for x in entries) else "FAIL", entries=entries))
    save("input-manifests.json", rows)
    im = Image()
    save("sections.json", im.sections)
    # Independently bind Gemini's otherwise unsealed local windows to both inputs.
    windows = []
    for p in sorted((ROOT / "research/body_v4_storage/gemini/local").glob("*.bin")):
        asm = p.with_suffix(".asm.txt")
        text = asm.read_text()
        m = re.search(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)", text, re.M)
        assert m, str(p)
        start, raw = int(m[1], 16), p.read_bytes()
        off = im.off(start, len(raw))
        count, bad = 0, []
        for line in text.splitlines():
            match = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)", line)
            if match:
                pc, decoded = int(match[1], 16), bytes.fromhex(match[2])
                count += len(decoded)
                if im.raw(pc, len(decoded)) != decoded:
                    bad.append(hex(pc))
        windows.append(dict(path=str(p.relative_to(ROOT)), start=hex(start), bytes=len(raw), sha256=sha(p),
                            official_equal=im.raw(start, len(raw)) == raw,
                            body_equal=im.body[off:off+len(raw)] == raw,
                            disassembly_bytes_with_overlap=count, disassembly_bad_addresses=bad))
    save("gemini-local-audit.json", dict(windows=windows,
         other_files=[dict(path=str(p.relative_to(ROOT)), sha256=sha(p), bytes=p.stat().st_size)
                      for p in sorted((ROOT / "research/body_v4_storage/gemini/local").rglob("*"))
                      if p.is_file() and p.suffix != ".bin"]))
    status = {"manifests": [{k: r[k] for k in ("manifest", "count", "status")} for r in rows],
              "protected_files": len(before), "gemini_bin_windows": len(windows),
              "gemini_all_bound": all(w["official_equal"] and w["body_equal"] and not w["disassembly_bad_addresses"] for w in windows)}
    print(json.dumps(status, ensure_ascii=False))

def collect():
    im = Image()
    plan = json.loads((ROOT / "research/body_v4_storage/gpt/windows.json").read_text())
    extra = [
        (0x2005dc00, 0x2005df00, "delay-wrapper"),
        (0x05002a00, 0x05002e00, "delay-kernel"),
        (0x20068900, 0x20069c70, "hardware-card-usb"),
        (0x20114548, 0x20114f00, "mount-format-helper"),
        (0x20155000, 0x20156300, "capture-counters"),
        (0x0500c500, 0x0500c800, "rtos-trap-stubs"),
        (0x050055cc, 0x05005838, "delay-service80"),
        (0x200d1600, 0x200d1838, "trap-dispatch-table"),
        (0x050021d4, 0x0500221c, "trap-dispatch"),
        (0x0500108c, 0x050010c4, "kernel-timer-link"),
        (0x20157c00, 0x20158500, "capture-workers"),
        (0x20171500, 0x20171674, "completion-send-front"),
        (0x20171f00, 0x20172b00, "capture-processing"),
        (0x20170950, 0x20170a10, "h09-comparison"),
        (0x20301800, 0x20301c00, "usb-mode-entry"),
        (0x20331800, 0x20331e00, "usb-ui-barrier"),
        (0x2035ae00, 0x2035b600, "format-ui"),
        (0x2036e900, 0x2036f400, "power-usb-transition"),
        (0x201c3800, 0x201c3c00, "usb-driver-entry"),
        (0x20374000, 0x20374600, "system-usb-entry"),
        (0x203b0e80, 0x203b1040, "direct-format-foreign"),
        (0x20141460, 0x201414a0, "card-volume-literal"),
        (0x200cf740, 0x200cf780, "irom-volume-literal"),
        (0x201d8fd0, 0x201d9260, "usb-claimed-driver-callee"),
    ]
    plan += [dict(start=hex(a), end=hex(b), label=n) for a, b, n in extra]
    rows = [im.dump(int(x["start"], 0), int(x["end"], 0), x["label"]) for x in plan]
    save("windows.json", rows)
    table = []
    for event in range(11):
        for state in range(3):
            at = 0x201427b4 + event*12 + state*4
            table.append(dict(event=event, state=state, address=hex(at), file=hex(im.off(at, 4)),
                              raw=im.raw(at, 4).hex(), handler=hex(int.from_bytes(im.raw(at, 4), "big"))))
    save("dispatch-table.json", table)
    print(json.dumps(dict(windows=len(rows), bytes=sum(r["bytes"] for r in rows),
                          unequal=[r["label"] for r in rows if not r["official_equals_body"]])))

def after():
    before = json.loads((OUT / "protected-before.json").read_text())
    changed = [rel for rel, row in before.items() if not (ROOT / rel).is_file() or sha(ROOT / rel) != row["sha256"]]
    new = sorted(set(str(p.relative_to(ROOT)) for p in protected_paths()) - set(before))
    extra_path=OUT/"supplemental-identities.json"
    extra=json.loads(extra_path.read_text())["files"] if extra_path.exists() else {}
    extra_changed=[rel for rel,row in extra.items() if not (ROOT/rel).is_file() or sha(ROOT/rel)!=row["sha256"]]
    save("protected-check.json", dict(status="PASS" if not changed and not new and not extra_changed else "FAIL",
                                      checked=len(before), changed=changed, new=new,
                                      supplemental_checked=len(extra), supplemental_changed=extra_changed))
    assert not changed and not new and not extra_changed, (changed, new, extra_changed)
    print("PASS protected files=" + str(len(before)))

def seal(check=False):
    manifest = HERE / "SHA256SUMS"
    paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p != manifest and "__pycache__" not in p.parts)
    content = "".join(sha(p) + "  " + str(p.relative_to(ROOT)) + "\n" for p in paths)
    if check:
        assert manifest.read_text() == content
        print("PASS SHA256SUMS entries=" + str(len(paths)))
    else:
        manifest.write_text(content)
        print("sealed entries=" + str(len(paths)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("init", "collect", "dump", "after", "seal", "check-seal"))
    ap.add_argument("rest", nargs="*")
    args = ap.parse_args()
    v = preflight()
    if args.action == "init":
        save("volume.json", v)
        init()
    elif args.action == "collect":
        collect()
    elif args.action == "dump":
        r = Image().dump(int(args.rest[0], 0), int(args.rest[1], 0), args.rest[2])
        index = OUT / "windows.json"
        rows = json.loads(index.read_text()) if index.exists() else []
        save("windows.json", [x for x in rows if x["label"] != r["label"]] + [r])
        print(json.dumps(r))
    elif args.action == "after":
        after()
    else:
        seal(args.action == "check-seal")

if __name__ == "__main__":
    main()
