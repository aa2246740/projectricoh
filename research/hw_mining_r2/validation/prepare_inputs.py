#!/usr/bin/env python3
"""核对本地研究输入，并保存官方成员副本。"""
import hashlib
import json
import struct
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
EXPECTED = {
    "gxr-151.zip": "3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898",
    "jlaunch3": "951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673",
    "ilaunch3": "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
}


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(name, value):
    p = OUT / name
    assert p.resolve().is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    archive = ROOT / "artifacts/downloads/gxr-151.zip"
    assert digest(archive) == EXPECTED[archive.name]
    sources = {str(archive.relative_to(ROOT)): digest(archive)}
    checks = []
    for label in ("gpt", "grok", "gemini"):
        base = OUT.parent / label
        manifest = base / "SHA256SUMS"
        count = 0
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            wanted, rel = line.split(maxsplit=1)
            p = (base / rel.lstrip(" *")).resolve()
            assert p.is_relative_to(base.resolve())
            actual = digest(p)
            assert actual == wanted, str(p)
            sources[str(p.relative_to(ROOT))] = actual
            count += 1
        checks.append({"report": label, "checked": count, "status": "OK"})
    for p in OUT.parent.rglob("*"):
        if p.is_file() and not p.is_relative_to(OUT):
            sources[str(p.relative_to(ROOT))] = digest(p)
    for p in [ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump",
              ROOT / "research/tooling_m32r/analyze_segments.py",
              ROOT / "research/isp_pipeline/analyze.py"]:
        sources[str(p.relative_to(ROOT))] = digest(p)
    prior = OUT / "inputs_before.json"
    if prior.exists():
        assert json.loads(prior.read_text()) == sources, "protected inputs changed"
    save("inputs_before.json", sources)
    extracted = []
    with zipfile.ZipFile(archive) as z:
        prefix = "GXR Update/Firmware rel 1.51/"
        inventory = [{"member": i.filename, "bytes": i.file_size, "crc32": f"{i.CRC:08x}"}
                     for i in z.infolist()]
        save("evidence/archive_inventory.json", inventory)
        for name in ("ilaunch3", "jlaunch0", "jlaunch3", "jlaunch4", "jlaunch8"):
            member = prefix + name
            data = z.read(member)
            sha = hashlib.sha256(data).hexdigest()
            if name in EXPECTED:
                assert sha == EXPECTED[name]
            p = OUT / "official" / name
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(data)
            sections = []
            for i, off in enumerate(range(0x20, 0x160, 20) if name.endswith("3") else ()):
                src, vma, size, bss, bss_size = struct.unpack_from(">IIIII", data, off)
                if not any((src, vma, size, bss, bss_size)):
                    break
                assert 0x200 + src + size <= len(data)
                sections.append({"index": i, "file_offset": 0x200 + src,
                                 "vma": vma, "size": size,
                                 "bss": bss, "bss_size": bss_size})
            extracted.append({"name": name, "member": member, "sha256": sha,
                              "bytes": len(data), "sections": sections})
    save("evidence/official_inputs.json", extracted)
    save("evidence/input_checks.json", {"archive": "OK", "report_manifests": checks,
                                       "protected_files": len(sources)})
    print(json.dumps({"archive": "OK", "reports": checks,
                      "protected_files": len(sources), "members": [x["name"] for x in extracted]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
