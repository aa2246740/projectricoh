"""Seal both permitted output trees and verify the resulting file manifests."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TOOLS = ROOT / "tools/gxr_emulator"
sys.path.insert(0, str(TOOLS))
from storage_run import sha


def paths(manifest, base):
    return [base / line.split("  ", 1)[1] for line in manifest.read_text().splitlines()]


def manifest(target, files, base):
    target.write_text("".join(sha(path)+"  "+str(path.relative_to(base))+"\n"
                              for path in sorted(set(files)) if path.is_file() and path != target))


def verify(target, base):
    bad, missing, total = [], [], 0
    for line in target.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = base / relative
        if not path.is_file():
            missing.append(relative)
        elif sha(path) != expected:
            bad.append(relative)
        total += 1
    return {"manifest": str(target.relative_to(ROOT)), "files": total,
            "mismatches": bad, "missing": missing, "sha256": sha(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "verify"))
    args = parser.parse_args()
    tool_target, research_target = TOOLS / "SHA256SUMS", HERE / "SHA256SUMS"
    if args.command == "seal":
        selected = paths(tool_target, TOOLS)+[path for path in TOOLS.iterdir() if path.is_file()]
        manifest(tool_target, selected, TOOLS)
        manifest(research_target, [path for path in HERE.rglob("*") if path.is_file()], ROOT)
    rows = [verify(tool_target, TOOLS), verify(research_target, ROOT)]
    research_paths = set(paths(research_target, ROOT))
    actual = {path for path in HERE.rglob("*") if path.is_file() and path != research_target}
    omitted = sorted(str(path.relative_to(ROOT)) for path in actual-research_paths)
    print(json.dumps({"manifests": rows, "research_omissions": omitted}, indent=2))
    return int(bool(omitted) or any(row["mismatches"] or row["missing"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
