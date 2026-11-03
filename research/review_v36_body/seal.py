"""Create a directory-relative SHA256SUMS, then verify every listed byte."""
import hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
manifest = HERE / "SHA256SUMS"
paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p != manifest)
assert all(not p.is_symlink() and p.resolve().is_relative_to(HERE) for p in paths)
lines = [hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(HERE).as_posix() + "\n" for p in paths]
manifest.write_text("".join(lines), encoding="ascii")
verified = set()
for line in manifest.read_text().splitlines():
    digest, rel = line.split("  ", 1)
    path = Path(rel)
    assert not path.is_absolute() and ".." not in path.parts
    assert hashlib.sha256((HERE / path).read_bytes()).hexdigest() == digest, rel
    verified.add(rel)
assert verified == {p.relative_to(HERE).as_posix() for p in HERE.rglob("*") if p.is_file() and p != manifest}
print("PASS directory-relative SHA256SUMS", len(verified), "files")
print("REVIEW.md", hashlib.sha256((HERE / "REVIEW.md").read_bytes()).hexdigest())
print("SHA256SUMS", hashlib.sha256(manifest.read_bytes()).hexdigest())
