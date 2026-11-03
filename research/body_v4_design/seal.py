#!/usr/bin/env python3
"""Repository-root-relative SHA256SUMS for this research only."""
from pathlib import Path
import argparse
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("body_v4_collect", HERE / "collect.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
MANIFEST = HERE / "SHA256SUMS"


def files():
    paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p != MANIFEST)
    assert all(not p.is_symlink() and p.resolve().is_relative_to(HERE) for p in paths)
    return paths


def main():
    a = argparse.ArgumentParser()
    a.add_argument("action", choices=("seal", "check"))
    args = a.parse_args()
    c.preflight()
    if args.action == "seal":
        MANIFEST.write_text("".join(f"{c.sha(p)}  {p.relative_to(c.ROOT)}\n" for p in files()))
    rows = {}
    for line in MANIFEST.read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = c.ROOT / name
        assert len(digest) == 64 and path.resolve().is_relative_to(HERE) and path != MANIFEST
        assert name not in rows, name
        rows[name] = digest
        assert c.sha(path) == digest, ("checksum mismatch", name)
    actual = {str(p.relative_to(c.ROOT)) for p in files()}
    assert set(rows) == actual, {"missing": sorted(actual-set(rows)), "extra": sorted(set(rows)-actual)}
    print("PASS SHA256SUMS", len(rows), "files; paths relative to repository root")


if __name__ == "__main__":
    main()
