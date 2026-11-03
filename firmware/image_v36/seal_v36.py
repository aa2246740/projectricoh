"""Verify frozen inputs and seal only the two authorized copies."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];REVIEW=HERE/'local/review'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def protect():
 before=json.loads((REVIEW/'protected-before.json').read_text());bad=[]
 for name,digest in before.items():
  p=ROOT/name
  if not p.is_file() or sha(p)!=digest:bad.append(name)
 result=dict(files=len(before),changed=bad,all_unchanged=not bad)
 (REVIEW/'protected-after.json').write_text(json.dumps(result,indent=2)+'\n')
 assert not bad,bad
 print('PROTECTED_UNCHANGED',len(before))
def seal(base):
 target=base/'SHA256SUMS'
 paths=[p for p in sorted(base.rglob('*')) if p.is_file() and p!=target]
 target.write_text(''.join(f'{sha(p)}  {p.relative_to(base).as_posix()}\n' for p in paths))
 for line in target.read_text().splitlines():
  digest,name=line.split('  ',1);assert not Path(name).is_absolute() and '..' not in Path(name).parts
  assert sha(base/name)==digest,name
 print('SHA256SUMS_PASS',base.relative_to(ROOT),len(paths))
def main():
 import sys
 if len(sys.argv)>1 and sys.argv[1]=='protect':protect();return
 seal(HERE/'local/package');seal(ROOT/'firmware/resident_v36');seal(HERE)
if __name__=='__main__':main()
