"""Verify fixed inputs and produce the two scoped delivery manifests."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path(__file__).resolve().parent
TOOLS = ROOT / "tools/gxr_emulator"


def digest(path, limit=None):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = limit
        while remaining is None or remaining:
            part = stream.read(min(1024 * 1024, remaining) if remaining is not None else 1024 * 1024)
            if not part:
                break
            value.update(part)
            if remaining is not None:
                remaining -= len(part)
    return value.hexdigest()


def guard():
    initial = json.loads((RESEARCH / "local/initial-inputs.json").read_text())
    permitted = {"tools/gxr_emulator/board_checks.py", "tools/gxr_emulator/CHANGES.md",
                 "tools/gxr_emulator/SHA256SUMS"}
    changed = [name for name, row in initial.items()
               if name not in permitted and digest(ROOT / name) != row["sha256"]]
    old = initial["tools/gxr_emulator/CHANGES.md"]
    prefix_ok = digest(TOOLS / "CHANGES.md", old["size"]) == old["sha256"]
    previous = ROOT / "research/emulator_m2b/SHA256SUMS"
    checked = 0
    mismatches = []
    for line in previous.read_text().splitlines():
        expected, name = line.split("  ", 1)
        if digest(ROOT / name) != expected:
            mismatches.append(name)
        checked += 1
    result = {"unchanged_initial_inputs": not changed,
              "initial_input_mismatches": changed, "changes_prefix_unchanged": prefix_ok,
              "m2b_files_checked": checked, "m2b_mismatches": mismatches}
    target = RESEARCH / "local/final-input-guard.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    if changed or not prefix_ok or mismatches:
        raise RuntimeError("fixed input guard differs")
    print(json.dumps(result))


def seal():
    original = {line.split("  ", 1)[1] for line in (TOOLS / "SHA256SUMS").read_text().splitlines()}
    original.update(p.name for p in TOOLS.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (TOOLS / "SHA256SUMS").write_text("".join(
        f"{digest(TOOLS / name)}  {name}\n" for name in sorted(original)))
    paths = sorted(p for p in RESEARCH.rglob("*") if p.is_file() and p.name != "SHA256SUMS"
                   and "__pycache__" not in p.parts and p.suffix != ".pyc")
    (RESEARCH / "SHA256SUMS").write_text("".join(
        f"{digest(p)}  {p.relative_to(ROOT)}\n" for p in paths))
    print(json.dumps({"tool_entries": len(original), "research_entries": len(paths)}))


def verify():
    counts = []
    for manifest, base in ((TOOLS / "SHA256SUMS", TOOLS), (RESEARCH / "SHA256SUMS", ROOT)):
        checked = 0
        names = set()
        for line in manifest.read_text().splitlines():
            expected, name = line.split("  ", 1)
            if digest(base / name) != expected:
                raise RuntimeError(f"manifest digest differs: {name}")
            checked += 1
            names.add(name)
        if manifest.parent == RESEARCH:
            actual = {str(path.relative_to(ROOT)) for path in RESEARCH.rglob("*")
                      if path.is_file() and path.name != "SHA256SUMS"
                      and "__pycache__" not in path.parts and path.suffix != ".pyc"}
            if names != actual:
                raise RuntimeError("research manifest file set differs")
        else:
            actual = {path.name for path in TOOLS.iterdir()
                      if path.is_file() and path.name != "SHA256SUMS"}
            if not actual.issubset(names):
                raise RuntimeError("tool manifest omits a root file")
        counts.append(checked)
    print(json.dumps({"verified": counts}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["guard", "seal", "verify"])
    args = parser.parse_args()
    {"guard": guard, "seal": seal, "verify": verify}[args.command]()


if __name__ == "__main__":
    main()
