#!/usr/bin/env python3
"""Write or verify this task's complete SHA256SUMS, including ignored local/."""
import argparse
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("card_container_pack", HERE / "pack.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


def inventory():
    result = {}
    for path in sorted(HERE.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not part of this task: {path}")
        if not path.is_file() or path == HERE/"SHA256SUMS":
            continue
        result[path.relative_to(HERE).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = inventory()
    if args.check:
        expected = {}
        for line in (HERE/"SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ", 1)
            if name in expected or len(digest) != 64:
                raise ValueError("invalid or duplicate checksum entry")
            expected[name] = digest
        changed = sorted(name for name in actual.keys() | expected.keys() if actual.get(name) != expected.get(name))
        if changed:
            parser.exit(1, "checksum mismatch: " + ", ".join(changed[:10]) + "\n")
        print(f"PASS SHA256SUMS files={len(actual)}")
    else:
        pack.preflight()
        target = HERE/"SHA256SUMS"
        if target.is_symlink():
            raise ValueError("refusing checksum symlink")
        target.write_text("".join(f"{digest}  {name}\n" for name, digest in actual.items()))
        print(f"WROTE SHA256SUMS files={len(actual)}")


if __name__ == "__main__":
    main()
