"""Write and verify research/emulator_batch/SHA256SUMS (repository-relative paths).

Covers this study (scripts, report, local evidence) and the batch tool copy
(sources, docs, rebuilt library); not third_party, build intermediates or
the list itself.
"""
import argparse
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools/gxr_emulator_batch"
LIST = HERE / "SHA256SUMS"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files():
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path != LIST and "__pycache__" not in path.parts:
            yield path
    for path in sorted(TOOLS.rglob("*")):
        rel = path.relative_to(TOOLS)
        if path.is_file() and rel.parts[0] not in ("third_party", "build", "tmp") \
                and "__pycache__" not in rel.parts:
            yield path
    yield TOOLS / "build/libgxr_m32r.dylib"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("seal", "verify"))
    args = parser.parse_args()
    if args.command == "seal":
        LIST.write_text("".join(f"{sha(p)}  {p.relative_to(ROOT)}\n" for p in files()))
        print("sealed", sum(1 for _ in LIST.read_text().splitlines()))
    else:
        bad = [rel for digest, rel in (line.split("  ", 1) for line in LIST.read_text().splitlines())
               if not (ROOT / rel).is_file() or sha(ROOT / rel) != digest]
        print({"files": len(LIST.read_text().splitlines()), "mismatches": bad})
        raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
