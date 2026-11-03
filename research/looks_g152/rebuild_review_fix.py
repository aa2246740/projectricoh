"""Build and identify the reviewed engine correction without changing inputs."""
from pathlib import Path
import difflib,hashlib,json,os,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    started=time.time_ns();steps=[]
    for script,args in [('build.py',['engine']),('layout_probe.py',[]),('package.py',[])]:
        at=time.time_ns();p=subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/script),*args],cwd=ROOT,capture_output=True,text=True,timeout=7200)
        (HERE/'review_fix/evidence'/('build-'+script+'.log')).write_text(p.stdout+p.stderr)
        p.check_returncode();steps.append(dict(script=script,started_ns=at,ended_ns=time.time_ns()))
        print(script,'PASS',flush=True)
    archive=HERE/'local/review-fix-prior';base=ROOT/'firmware/engine_v60_g152';changes=[];diff=[]
    for p in base.rglob('*'):
        if not p.is_file() or 'local' in p.parts or p.is_symlink():continue
        old=archive/p.relative_to(ROOT)
        assert old.is_file(),str(p)
        if sha(p)!=sha(old):
            changes.append(dict(path=str(p.relative_to(ROOT)),old_sha256=sha(old),new_sha256=sha(p)))
            diff.extend(difflib.unified_diff(old.read_text().splitlines(True),p.read_text().splitlines(True),fromfile=str(p.relative_to(ROOT))+'.before',tofile=str(p.relative_to(ROOT))))
    assert len(changes)==1 and changes[0]['path'].endswith('/eng_core.c'),changes
    (HERE/'review_fix/engine-change.diff').write_text(''.join(diff))
    package=json.loads((HERE/'package.json').read_text())
    result=dict(status='PASS',started_ns=started,ended_ns=time.time_ns(),steps=steps,engine_changes=changes,package=package)
    (HERE/'review_fix/build.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','engine_changes','ended_ns')}),flush=True)
if __name__=='__main__':main()
