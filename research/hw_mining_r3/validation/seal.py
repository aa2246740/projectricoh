#!/usr/bin/env python3
"""生成覆盖本目录的 SHA-256 清单，并逐项读回核对。"""
import hashlib
import json
import runpy
from pathlib import Path

OUT=Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    check=runpy.run_path(str(OUT/'verify.py'))
    result=check['verify']()
    check['S']['save']('evidence/verification.json',result)
    files=[p for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'SHA256SUMS']
    assert all(not p.is_symlink() for p in files)
    manifest=OUT/'SHA256SUMS'
    manifest.write_text(''.join(f'{sha(p)}  {p.relative_to(OUT).as_posix()}\n' for p in files))
    listed=[]
    for line in manifest.read_text().splitlines():
        expected,name=line.split('  ',1)
        p=(OUT/name).resolve()
        assert p.is_relative_to(OUT) and sha(p)==expected,name
        listed.append(name)
    actual=[p.relative_to(OUT).as_posix() for p in sorted(OUT.rglob('*'))
            if p.is_file() and p!=manifest]
    assert listed==actual
    print(json.dumps(dict(status='PASS',files=len(listed),all_checksums='OK',
                          manifest_sha256=sha(manifest)),ensure_ascii=False))


if __name__=='__main__':
    main()
