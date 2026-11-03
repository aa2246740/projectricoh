"""Check actual task dependencies against the original, unmodified whole-repo freeze.

Keep the failed global comparison intact. Concurrent unrelated repository work
does not justify replacing the original freeze or restoring somebody's files.
"""
from pathlib import Path
import collections
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save

SCOPES=(
 'firmware', 'tools', 'artifacts/firmware', 'artifacts/downloads/gxr-151.zip',
 'research/review_g118', 'research/ux_preview_dot_r1', 'research/review_g117_codegen',
 'research/review_g117_codegen_r2', 'research/review_g117_container', 'research/review_v36_body',
 'research/review_v35_body', 'research/cpu_speed_r1', 'research/t_persistence', 'research/t_recovery',
 'research/tooling_m32r', 'research/tooling_m32r_asm', 'research/tooling_m32r_c',
)

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def covered(name):return any(name==scope or name.startswith(scope+'/') for scope in SCOPES)

def main():
    before=json.loads((OUT/'inputs-before.json').read_text());global_check=json.loads((OUT/'input-integrity.json').read_text())
    inputs={k:v for k,v in before.items() if covered(k)};changes={}
    for name,expected in inputs.items():
        p=ROOT/name
        actual=['symlink',str(p.readlink())] if p.is_symlink() else [p.stat().st_size,digest(p)] if p.is_file() else None
        if actual!=expected:changes[name]=dict(before=expected,after=actual)
    global_changes=global_check['changes']
    within={k:v for k,v in global_changes.items() if covered(k)}
    assert not within,('global snapshot reports changed task dependency',list(within)[:10])
    summary=dict(status='PASS' if not changes else 'FAIL',unchanged=not changes,files=len(inputs),changes=changes,scopes=SCOPES,
        original_freeze_replaced=False,global_snapshot_unchanged=global_check['unchanged'],global_snapshot_changes=len(global_changes),
        global_change_prefixes=dict(collections.Counter('/'.join(Path(k).parts[:2]) for k in global_changes)),
        note='The global mismatch remains in input-integrity.json. No unrelated path is reverted. This report checks named task dependencies against their original hashes, not a new baseline.')
    save('protected-input-integrity.json',summary)
    assert not changes,list(changes)[:10]
    print('PASS protected task inputs',len(inputs),'; global mismatch preserved',len(global_changes),flush=True)

if __name__=='__main__':main()
