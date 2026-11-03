"""Audit frozen inputs and remove only this review's exact Scratch directory."""
import argparse, json, os, shutil, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cleanup',action='store_true');args=parser.parse_args()
    guard(False);before=json.loads((HERE/'evidence/frozen-inputs.json').read_text());after=frozen()
    changed=[dict(path=k,before=before.get(k),after=after.get(k)) for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
    extra=json.loads((HERE/'evidence/supplemental-inputs.json').read_text());drift=[]
    extra.update(json.loads((HERE/'evidence/additional-used-inputs.json').read_text()))
    for relative,digest in extra.items():
        path=ROOT/relative;actual=sha(path.read_bytes()) if path.is_file() else None
        if actual!=digest:drift.append(dict(path=relative,before=digest,after=actual))
    save('evidence/final-input-audit.json',dict(status='PASS' if not changed and not drift else 'FAIL',
         initial_entries=len(before),supplemental_entries=len(extra),initial_changes=changed,supplemental_changes=drift))
    assert not changed and not drift,(changed,drift)
    if args.cleanup:
        assert TMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-looks18-r1') and not TMP.is_symlink()
        # This command is called after all bounded jobs have exited. No broad
        # Scratch sweep, parent-directory removal, card path, or Git mutation.
        count=sum(p.is_file() for p in TMP.rglob('*')) if TMP.exists() else 0
        size=sum(p.stat().st_size for p in TMP.rglob('*') if p.is_file()) if TMP.exists() else 0
        if TMP.exists():shutil.rmtree(TMP)
        assert not TMP.exists()
        save('evidence/cleanup.json',dict(status='PASS',scratch=str(TMP),removed=True,files_removed=count,bytes_removed=size,
             after_exists=TMP.exists(),scope='Only the exact review Scratch directory'))
    print(json.dumps(dict(status='PASS',initial_entries=len(before),supplemental_entries=len(extra),cleanup=args.cleanup)))

if __name__=='__main__':main()
