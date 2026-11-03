"""Offline SD evidence windows and fixed-input records."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
TOOLS = ROOT / "tools/gxr_emulator"
sys.path.insert(0, str(TOOLS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    OUT.mkdir(exist_ok=True)
    target = OUT / "initial-inputs.json"
    if target.exists():
        raise ValueError("initial record already exists")
    files = [ROOT / "artifacts/firmware/gxr-1.51/ilaunch3",
             ROOT / "artifacts/firmware/gxr-1.51/jlaunch3",
             TOOLS / "build/libgxr_m32r.dylib"]
    files += sorted(p for p in TOOLS.iterdir() if p.is_file())
    rows = {str(p.relative_to(ROOT)): {"size": p.stat().st_size, "sha256": sha(p)}
            for p in files}
    target.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"files": len(rows), "output": str(target)}))


def window(start, end):
    from image import Image
    image = Image()
    OUT.mkdir(exist_ok=True)
    lines = []
    selected = [s for s in image.sections if s["load_address"] < end and
                s["load_address"] + s["initialized_size"] > start]
    for section in selected:
        matches = list((ROOT / "research/tooling_m32r/disasm").glob(
            f"ilaunch3-sec{section['index']:02d}-*.disasm.txt"))
        if len(matches) != 1:
            raise ValueError("native disassembly section is not unique")
        p = matches[0]
        for line in p.read_text().splitlines():
            match = re.match(r"^\s*([0-9a-f]{7,8}):\s*((?:[0-9a-f]{2} )+)\s*(.*)$", line)
            if not match or not start <= int(match[1], 16) < end:
                continue
            address = int(match[1], 16)
            data = bytes.fromhex(match[2])
            offset = image.offset(address, len(data))
            if image.raw[offset:offset + len(data)] != data:
                raise ValueError("disassembly bytes differ from official image")
            lines.append(line)
    path = OUT / f"window-{start:08x}-{end:08x}.txt"
    path.write_text("\n".join(lines) + "\n")
    print(json.dumps({"window": str(path), "instructions": len(lines),
                      "image_sha256": image.sha256, "sha256": sha(path)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "window"])
    parser.add_argument("start", nargs="?", type=lambda v: int(v, 0))
    parser.add_argument("end", nargs="?", type=lambda v: int(v, 0))
    args = parser.parse_args()
    if args.command == "freeze":
        freeze()
    else:
        window(args.start, args.end)


if __name__ == "__main__":
    main()
