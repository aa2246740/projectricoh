"""Finalize only after all mandatory checks; freeze package and scoped evidence."""
from pathlib import Path
import hashlib,json,subprocess,sys,os
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'local';C=HERE/'candidate';PACKAGE=ROOT/'firmware/package_v35_g117'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(name,argv,cwd=ROOT):
 p=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,text=True,env=dict(os.environ,TMPDIR=str(C/'local/tmp'),PYTHONDONTWRITEBYTECODE='1'),timeout=180)
 (OUT/(name+'.stdout')).write_text(p.stdout);(OUT/(name+'.stderr')).write_text(p.stderr)
 if p.returncode:raise RuntimeError(name+': '+p.stderr[-1800:]+p.stdout[-1800:])
 print(p.stdout.strip(),flush=True)
 return p

def main():
 native=json.loads((OUT/'native-runs.json').read_text());assert len(native)==2 and all(r['returncode']==0 for r in native)
 stages=json.loads((OUT/'host-stages.json').read_text());assert len(stages)==26 and all(r['returncode']==0 for r in stages)
 static=json.loads((OUT/'static/summary.json').read_text());assert static['status']=='PASS'
 dat=C/'local/full-r13/GXRCE.DAT';assert sha(dat)=='4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a'==static['sha256']
 assert not (OUT/'conformance.stderr').read_text() and (OUT/'conformance.stdout').read_text().startswith('PASS ')
 assert not (OUT/'native-probe.stderr').read_text() and 'cases 29' in (OUT/'native-probe.stdout').read_text()
 assert sha(HERE/'native_harness/conformance.py')==sha(ROOT/'tools/native_harness/conformance.py')
 assert sha(HERE/'native_harness/scenarios.py')==sha(ROOT/'tools/native_harness/scenarios.py')
 # Actual resident copy stayed a read-only starting point. No resident build
 # was emitted by this task; the checked body remains the exact supplied one.
 for src in (ROOT/'firmware/engine_v37/resident').iterdir():
  if src.is_file():assert src.read_bytes()==(HERE/'resident'/src.name).read_bytes(),src
 before=json.loads((OUT/'inputs-before.json').read_text())
 changed=[dict(path=p,expected=h,actual=sha(ROOT/p) if (ROOT/p).is_file() else None) for p,h in before.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
 (OUT/'protected-after.json').write_text(json.dumps(dict(files=len(before),changed=changed),indent=2)+'\n')
 assert not changed,changed
 print('PASS protected inputs',len(before),'content changes=0',flush=True)
 call('report-generate',['/usr/bin/python3','-I','-B',HERE/'write_report117.py'])
 call('package-final',['/usr/bin/python3','-I','-B',HERE/'package117.py','--sums'])
 result=call('sha256-check',['/usr/bin/shasum','-a','256','-c','SHA256SUMS'],cwd=PACKAGE)
 assert len(result.stdout.splitlines())==31 and all(s.endswith(': OK') for s in result.stdout.splitlines())
 # Hash rerunnable sources and final receipts. Compiler temporary files and
 # decoder caches are reproducible intermediates, not acceptance evidence.
 paths=[]
 for p in HERE.rglob('*'):
  if not p.is_file() or p.is_symlink() or p.name=='EVIDENCE_SHA256SUMS' or p.name.startswith('final-verify.'):continue
  rel=p.relative_to(HERE)
  if any(part in ('tmp','decode','__pycache__') or part.startswith('host-attempt') for part in rel.parts):continue
  paths.append(p)
 (HERE/'EVIDENCE_SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(HERE).as_posix()+'\n' for p in sorted(paths)))
 print('PASS gen117 final package checks; evidence hashes',len(paths),flush=True)
if __name__=='__main__':main()
