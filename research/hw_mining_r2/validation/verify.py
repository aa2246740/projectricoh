#!/usr/bin/env python3
"""核验官方字节、原输入和本目录清单。"""
import argparse
import datetime
import hashlib
import json
import re
import runpy
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
MANIFEST = OUT / "SHA256SUMS"


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def files():
    result = []
    for p in OUT.rglob("*"):
        assert not p.is_symlink(), p
        if p.is_file() and p != MANIFEST:
            result.append(p)
    return sorted(result, key=lambda z: z.relative_to(OUT).as_posix())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    before = json.loads((OUT / "inputs_before.json").read_text())
    for rel, expected in before.items():
        p = ROOT / rel
        assert not p.resolve().is_relative_to(OUT)
        assert digest(p) == expected, rel
    records = json.loads((OUT / "evidence/official_inputs.json").read_text())
    with zipfile.ZipFile(ROOT / "artifacts/downloads/gxr-151.zip") as archive:
        for rec in records:
            data = archive.read(rec["member"])
            assert hashlib.sha256(data).hexdigest() == rec["sha256"]
            assert data == (OUT / "official" / rec["name"]).read_bytes()
    x = runpy.run_path(str(OUT / "audit.py"))
    ims = {name: x["Image"](name) for name in ("jlaunch3", "ilaunch3", "jlaunch0")}
    windows = raw_windows = asm_files = asm_lines = asm_bytes = 0
    unrendered = []
    pattern = re.compile(r"^\s*([0-9a-f]{7,8}):\s+((?:[0-9a-f]{2} ){1,4})\s*(.*)")
    for folder in ("disasm", "evidence"):
        for meta_path in sorted((OUT / folder).glob("*.json")):
            meta = json.loads(meta_path.read_text())
            if not isinstance(meta, dict) or not {"image", "end", "file_offset", "sha256"} <= meta.keys():
                continue
            if "start" not in meta and "vma" not in meta:
                continue
            im = ims[meta["image"]]
            start = int(meta.get("start", meta.get("vma")), 0)
            end = int(meta["end"], 0)
            raw_path = meta_path.with_suffix(".bin")
            data = raw_path.read_bytes()
            assert data == im.read(start, end - start), str(raw_path)
            assert digest(raw_path) == meta["sha256"]
            assert im.offset(start) == int(meta["file_offset"], 0)
            asm_path = meta_path.with_suffix(".asm")
            if not asm_path.exists():
                raw_windows += 1
                continue
            cursor = start
            count = size = 0
            listing = asm_path.read_text()
            for line in listing.splitlines():
                m = pattern.match(line)
                if not m:
                    continue
                addr = int(m[1], 16)
                code = bytes.fromhex(m[2])
                assert addr == cursor, (str(asm_path), hex(addr), hex(cursor))
                assert im.read(addr, len(code)) == code, (str(asm_path), hex(addr))
                cursor += len(code)
                size += len(code)
                count += 1
            if cursor != end:
                assert folder == "disasm" and 0 < end - cursor < 4
                assert f"Address 0x{cursor:x} is out of bounds." in listing
                tail = im.read(cursor, end - cursor)
                unrendered.append({"listing": str(asm_path.relative_to(OUT)), "image": im.name,
                    "vma": hex(cursor), "file_offset": hex(im.offset(cursor)), "bytes": tail.hex(),
                    "reason": "GNU objdump 原输出在段末报告边界；完整原字节另由 bin 对照。"})
            assert count and size + end - cursor == len(data)
            asm_files += 1
            asm_lines += count
            asm_bytes += size
            windows += folder == "evidence"
    assert asm_files == 33 + 25
    assert windows == 25 and raw_windows == 6
    checks = json.loads((OUT / "evidence/byte-assertions.json").read_text())
    for row in checks:
        address = int(row["vma"], 0)
        data = bytes.fromhex(row["bytes"])
        assert ims["jlaunch3"].read(address, len(data)) == data
        assert ims["jlaunch3"].offset(address) == int(row["file_offset"], 0)
    repeated = json.loads((OUT / "evidence/k3-strict-repeated.json").read_text())
    assert repeated["matches_original_output"] and repeated["section_csv_matches_header"]
    assert repeated["mapped_sections"] == 16 and repeated["mapped_bytes"] == 2480650
    assert len(repeated["hits"]) == 13
    refs = json.loads((OUT / "evidence/k2-k4-references.json").read_text())["targets"]
    for target in ("0x201123b0", "0x201123d4"):
        assert all(not value for value in refs[target].values())
    assert [c["pc"] for c in refs["0x20255600"]["constant_calls"]
            if c["registers"].get("r4") == "0xb"] == ["0x201123e0"]
    report = (OUT / "VALIDATION.md").read_text()
    result_path = OUT / "evidence/verification.json"
    local_links = []
    quoted = 0
    for match in re.finditer(r"^([0-9A-F]{8}): ((?:[0-9a-f]{2} ){4})", report, re.MULTILINE):
        address = int(match[1], 16)
        code = bytes.fromhex(match[2])
        assert ims["jlaunch3"].read(address, len(code)) == code, hex(address)
        quoted += 1
    assert report.startswith("需要修正。")
    assert report.rstrip().splitlines()[-1].startswith("GXR 是否存在可按配方修改的曲线前 3×3：未定")
    for match in re.finditer(r"\]\(([^)]+)\)", report):
        link = match[1].split("#", 1)[0]
        if link and "://" not in link:
            target = (OUT / link).resolve()
            assert target.exists() or (args.seal and target in (result_path, MANIFEST)), link
            local_links.append(target)
    result = {"status": "PASS", "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "protected_input_files_unchanged": len(before), "official_members_checked": len(records),
              "disassembly_files_checked": asm_files, "disassembly_lines_checked": asm_lines,
              "disassembly_bytes_checked": asm_bytes, "code_windows_checked": windows,
              "unrendered_segment_tails": unrendered,
              "raw_windows_checked": raw_windows, "explicit_byte_assertions": len(checks),
              "report_byte_excerpts_checked": quoted,
              "original_strict_scan_matches": True,
              "scope": "静态字节、数据来源和交付完整性；没有目标执行或相机像素验收。",
              "sha256_file_count": len([p for p in files() if p != result_path]) + 1}
    if args.seal:
        x["save"]("evidence/verification.json", result)
        MANIFEST.write_text("".join(digest(p) + "  " + p.relative_to(OUT).as_posix() + "\n" for p in files()))
    assert MANIFEST.exists()
    entries = {}
    for line in MANIFEST.read_text().splitlines():
        expected, rel = line.split("  ", 1)
        p = (OUT / rel).resolve()
        assert p.is_relative_to(OUT) and p != MANIFEST and rel not in entries
        assert digest(p) == expected, rel
        entries[rel] = expected
    assert set(entries) == {p.relative_to(OUT).as_posix() for p in files()}
    assert len(entries) == result["sha256_file_count"]
    assert all(p.exists() for p in local_links)
    print(f"PASS: {len(entries)} SHA256SUMS entries OK; {len(before)} protected inputs unchanged")
    print(f"{asm_files} listings, {asm_lines} byte-checked lines, {len(checks)} explicit assertions")
    print(f"Native listing tails recorded: {sum(len(bytes.fromhex(t['bytes'])) for t in unrendered)} bytes")


if __name__ == "__main__":
    main()
