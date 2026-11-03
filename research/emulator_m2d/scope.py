"""Freeze inputs and check the permitted source changes."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "local"
TOOLS = ROOT / "tools/gxr_emulator"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files():
    selected = list(TOOLS.glob("*"))
    selected += [TOOLS / "build/libgxr_m32r.dylib", ROOT / ".gitignore"]
    selected += list((ROOT / "artifacts/firmware/gxr-1.51").glob("*"))
    for name in ("emulator_m2b", "emulator_m2c"):
        selected += list((ROOT / "research" / name).glob("*"))
    for name in ("emulator_m2b/local/stable-final-r1-stop.pkl",
                 "emulator_m2c/local/cold-card-final-r1-stop.pkl",
                 "emulator_m2b/local/nand-reflector.pages.json",
                 "emulator_m2b/local/unit-info-synthetic.bin"):
        selected.append(ROOT / "research" / name)
    return sorted({p for p in selected if p.is_file()})


def main():
    OUT.mkdir(exist_ok=True)
    initial = OUT / "initial-inputs.json"
    if sys.argv[1] == "freeze":
        if initial.exists():
            raise ValueError("initial input record exists")
        rows = {str(p.relative_to(ROOT)): {"size": p.stat().st_size, "sha256": sha(p)}
                for p in files()}
        initial.write_text(json.dumps(rows, indent=2) + "\n")
        print(json.dumps({"frozen_files": len(rows)}))
        return
    rows = json.loads(initial.read_text())
    editable = {"tools/gxr_emulator/board.py", "tools/gxr_emulator/peripherals.py",
                "tools/gxr_emulator/sdcard.py", "tools/gxr_emulator/fat_image.py",
                "tools/gxr_emulator/SHA256SUMS"}
    differences = []
    for name, row in rows.items():
        path = ROOT / name
        if name == "tools/gxr_emulator/CHANGES.md":
            actual = hashlib.sha256(path.read_bytes()[:row["size"]]).hexdigest()
        else:
            actual = sha(path)
        if actual != row["sha256"] and name not in editable:
            differences.append(name)
    result = {"unchanged_inputs": not differences, "differences": differences,
              "files": len(rows), "allowed_existing_changes": sorted(editable),
              "changes_prefix_unchanged": hashlib.sha256((TOOLS / "CHANGES.md").read_bytes()[
                  :rows["tools/gxr_emulator/CHANGES.md"]["size"]]).hexdigest()
                  == rows["tools/gxr_emulator/CHANGES.md"]["sha256"]}
    history = []
    for milestone in ("emulator_m2b", "emulator_m2c"):
        manifest = ROOT / "research" / milestone / "SHA256SUMS"
        bad, count = [], 0
        for line in manifest.read_text().splitlines():
            expected, relative = line.split("  ", 1)
            path = ROOT / relative
            if not path.is_file() or sha(path) != expected:
                bad.append(relative)
            count += 1
        history.append({"milestone": milestone, "files": count, "mismatches": bad,
                        "manifest_sha256": sha(manifest)})
    result["historical_manifests"] = history
    result["historical_inputs_unchanged"] = not any(row["mismatches"] for row in history)
    (OUT / "final-input-guard.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if differences or not result["historical_inputs_unchanged"] or not result["changes_prefix_unchanged"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
