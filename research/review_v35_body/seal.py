"""Seal all review files with directory-relative SHA-256 paths, then verify."""
import hashlib
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
manifest=HERE/"SHA256SUMS"
files=sorted(p for p in HERE.rglob("*") if p.is_file() and p!=manifest)
assert not any(p.is_symlink() for p in HERE.rglob("*"))
lines=[]
for p in files:
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    name=p.relative_to(HERE).as_posix()
    assert not name.startswith("/") and "\n" not in name
    lines.append(f'{digest}  {name}\n')
manifest.write_text("".join(lines),encoding="utf-8")
for line in manifest.read_text().splitlines():
    expected,name=line.split("  ",1)
    p=(HERE/name).resolve();p.relative_to(HERE)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,name
report=(HERE/"REVIEW.md").read_text()
for name in re.findall(r'\]\(([^)]+)\)',report):
    assert (HERE/name).is_file(),name
assert report.startswith("不可以上卡")
print(f'VERIFIED {len(files)} files; relative SHA256SUMS; all report links exist')
