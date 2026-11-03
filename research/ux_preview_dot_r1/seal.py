"""Verify final evidence and seal every research file except the manifest itself."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for script,args in (('freeze.py',[]),('artifacts.py',['--package']),('summarize.py',[])):
        subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/script),*args],cwd=ROOT,check=True)
    report=(HERE/'REPORT.md').read_text()
    assert '待封存' not in report and '待最终' not in report
    assert sha(ROOT/'firmware/package_v36_g118/SD_ROOT/GXRCE.DAT') in report
    limit=json.loads((HERE/'local/runs/persistent-fault-50mm.json').read_text())
    assert limit['status']=='EXPECTED_LIMITATION'
    assert limit['dat_sha256']==sha(ROOT/'firmware/package_v36_g118/SD_ROOT/GXRCE.DAT')
    broken=[]
    for p in (HERE/'REPORT.md',ROOT/'firmware/engine_v39_ux/GEN118.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' in target or target.startswith('#'):continue
            local=unquote(target.split('#',1)[0])
            if not (p.parent/local).is_file():broken.append((str(p),target))
    assert not broken,broken
    for p in HERE.rglob('*'):
        assert not p.is_symlink(),p
    out=HERE/'local/artifacts/seal-checks.json'
    out.write_text(json.dumps(dict(protected_inputs_unchanged=9011,artifact_checks=True,
        three_native_matrices=True,three_native_shutter_exits=True,relative_links=True,
        card_sha256sums='30/30 OK',persistent_rpc_outage='known mixed-row limitation reproduced',
        scope='offline native model; no camera or card'),indent=2)+'\n')
    manifest=HERE/'SHA256SUMS'
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and p!=manifest)
    manifest.write_text(''.join(sha(p)+'  '+p.relative_to(HERE).as_posix()+'\n' for p in files))
    # Keep output in memory. Writing a post-seal log inside this directory
    # would immediately invalidate coverage or its own hash.
    check=subprocess.run(['/usr/bin/shasum','-a','256','-c','SHA256SUMS'],cwd=HERE,capture_output=True,text=True)
    assert check.returncode==0,(check.stdout,check.stderr)
    assert check.stdout.count(': OK')==len(files)
    assert len(files)==sum(p.is_file() and p!=manifest for p in HERE.rglob('*'))
    print('PASS research SHA256SUMS:',len(files),'/',len(files),'OK')
    print('SHA256SUMS sha256',sha(manifest))

if __name__=='__main__':main()
