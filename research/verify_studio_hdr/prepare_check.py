"""Prepare local build cache and redirect the one tool without a cache environment option."""
import json
import os
import shutil
from pathlib import Path

TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')
OUT = Path(__file__).resolve().parent
source = Path('/Users/wu/.cache/uv')
target = TMP / 'uv-cache'
target.mkdir(exist_ok=True)
names = ['hatchling', 'packaging', 'pathspec', 'pluggy', 'trove-classifiers', 'tomlkit']
copied = []
simple = source / 'simple-v17'
if simple.exists():
    shutil.copytree(simple, target / 'simple-v17', dirs_exist_ok=True)
for name in names:
    origin = source / 'wheels-v5/pypi' / name
    dest = target / 'wheels-v5/pypi' / name
    dest.mkdir(parents=True, exist_ok=True)
    for p in origin.iterdir():
        q = dest / p.name
        if p.is_symlink():
            actual = p.resolve()
            archive = target / 'archive-v0' / actual.name
            shutil.copytree(actual, archive, dirs_exist_ok=True)
            if not q.exists():
                q.symlink_to(archive, target_is_directory=True)
            copied.append(str(p.relative_to(source)))
        elif p.is_file():
            shutil.copy2(p, q)
        elif p.is_dir():
            shutil.copytree(p, q, dirs_exist_ok=True)
bin_dir = TMP / 'bin'
bin_dir.mkdir(exist_ok=True)
wrapper = bin_dir / 'uv'
wrapper.write_text('''#!/usr/bin/python3 -B
import os
import sys
args = sys.argv[1:]
if args[:3] == ["run", "--frozen", "lint-imports"]:
    args += ["--cache-dir", "/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr/import-cache"]
os.execv("/opt/homebrew/bin/uv", ["uv", *args])
''')
wrapper.chmod(0o700)
count = 0
size = 0
for base, _, files in os.walk(target):
    for n in files:
        p = Path(base) / n
        if not p.is_symlink():
            count += 1
            size += p.stat().st_size
receipt = {'cache_wheels': copied, 'files': count, 'bytes': size, 'wrapper_purpose': 'import-linter cache directory only'}
(OUT / 'check_preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
