#!/usr/bin/env python3
"""Hash this task's complete delivery, including ignored evidence, then verify."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('checksum_preflight',HERE/'inspect.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.preflight()
excluded={'SHA256SUMS','local/checksums-check.log'}
files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.relative_to(HERE).as_posix() not in excluded)
for p in files:
    assert not p.is_symlink(),p
sums=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE).as_posix()}\n' for p in files)
(HERE/'SHA256SUMS').write_text(sums)
result=subprocess.run(['shasum','-a','256','-c','SHA256SUMS'],cwd=HERE,text=True,capture_output=True)
(HERE/'local/checksums-check.log').write_text(result.stdout+result.stderr)
assert result.returncode==0,result.stderr
print(f'PASS_SHA256 files={len(files)}')
