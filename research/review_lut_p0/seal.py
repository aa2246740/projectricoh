"""Seal and verify this review's files, without changing protected inputs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_freeze',HERE/'review.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def check():
    manifest=HERE/'SHA256SUMS'
    wanted={}
    for line in manifest.read_text().splitlines():
        value,name=line.split('  ',1)
        wanted[name]=value
    files={str(p.relative_to(HERE)):p for p in HERE.rglob('*') if p.is_file() and p!=manifest}
    assert files.keys()==wanted.keys(),'review file list changed'
    assert all(f.digest(path)==wanted[name] for name,path in files.items()),'review digest mismatch'
    print('PASS SHA256SUMS files='+str(len(files)))


if __name__=='__main__':
    f.freeze()
    if sys.argv[1:]==['--check']:
        check()
    else:
        baseline=json.loads((HERE/'protected-inputs.json').read_text())
        active={p:v for p,v in baseline.items() if not p.startswith(f.EXCLUDED_LIVE)}
        assert f.snapshot()==active
        (HERE/'frozen-verification.json').write_text(json.dumps(dict(
            status='PASS',protected_files=len(active),changed=[],
            excluded_live_cache_baseline_entries=len(baseline)-len(active),
            original_baseline_sha256=f.digest(HERE/'protected-inputs.json'),
            excluded_live_prefixes=list(f.EXCLUDED_LIVE),decisions_tsv_excluded=True),indent=2)+'\n')
        manifest=HERE/'SHA256SUMS'
        files=sorted(p for p in HERE.rglob('*') if p.is_file() and p!=manifest)
        assert not any(p.is_symlink() for p in files)
        manifest.write_text(''.join(f.digest(p)+'  '+str(p.relative_to(HERE))+'\n' for p in files))
        check()
