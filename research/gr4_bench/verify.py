#!/usr/bin/env python3
"""Read-only verification of public/local checksums, ignore fence, and inputs."""
import ast
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()


def sums(base, path, public=False):
    seen=set()
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'): continue
        expected,name=line.split(maxsplit=1); name=name.lstrip('*')
        p=(base/name).resolve()
        assert p.is_relative_to(base) and p.is_file() and not (base/name).is_symlink(),name
        assert re.fullmatch('[0-9a-f]{64}',expected) and sha(p)==expected,name
        assert name not in seen,name
        seen.add(name)
    actual={str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()
            and p!=path and (not public or not p.is_relative_to(LOCAL))}
    assert seen==actual,dict(missing=sorted(actual-seen),extra=sorted(seen-actual))
    return len(seen)


def main():
    info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and info['MountPoint']=='/Volumes/Workspace'
    assert info['FilesystemType']=='apfs' and info['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(info.get(k) for k in ('Writable','WritableMedia','WritableVolume'))
    assert (HERE/'.gitignore').read_text()=='local/\n' and not LOCAL.is_symlink()
    ignore=subprocess.check_output(['git','check-ignore','-v','research/gr4_bench/local/x'],cwd=ROOT,text=True)
    assert ignore.startswith('research/gr4_bench/.gitignore:1:local/')
    public=sums(HERE,HERE/'SHA256SUMS',True)
    private=sums(LOCAL,LOCAL/'SHA256SUMS')
    inputs=json.loads((LOCAL/'input_ledger.json').read_text())
    for name,expected in inputs.items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and not path.is_relative_to(HERE)
        assert sha(path)==expected,f'Input modified: {name}'
    fits=list((LOCAL/'fits').rglob('*.json'))
    assert len(fits)==192,len(fits)
    converged=0
    for path in fits:
        rec=json.loads(path.read_text())
        assert all(rec.get(key) is False for key in ('accepted','firmware_ready','deployable'))
        assert rec['curve_unchanged'] and rec['other_fields_unchanged'] and not rec['T1_enabled']
        assert sum(rec['row_coef'][0])==1024 and len(rec['A'])==len(rec['B'])==24
        converged+=rec['solve']['success']
    assert not any(p.suffix.upper()=='.DAT' for p in HERE.rglob('*'))
    for path in HERE.iterdir():
        if not path.is_file():continue
        assert path.name in ('.gitignore','SHA256SUMS','REPORT.md') or path.suffix=='.py'
        if path.suffix=='.py':
            tree=ast.parse(path.read_text(),filename=str(path))
            assert not any(isinstance(n,ast.Constant) and isinstance(n.value,bytes) and len(n.value)>=48
                           for n in ast.walk(tree))
    print(json.dumps(dict(public_files=public,local_files=private,unchanged_inputs=len(inputs),
          ignore_rule=ignore.strip(),integer_candidates=len(fits),converged=converged,
          unconverged=len(fits)-converged,no_DAT=True,checksums_and_input_integrity='PASS'),ensure_ascii=False))


if __name__=='__main__': main()
