"""Verify delivery, remove only task Scratch, and seal reproducible receipts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def package_check():
    manifest=json.loads((PACKAGE/'MANIFEST.json').read_text())
    root=PACKAGE/'local/SD_ROOT';raw=root/'GXRCE.DAT';archive=PACKAGE/'local/GXR-probe2.zip'
    assert digest(raw)==manifest['dat_sha256'] and raw.stat().st_size==manifest['dat_bytes']
    assert digest(archive)==manifest['archive_sha256']
    assert {p.name for p in root.iterdir()}=={'GXRCE.DAT','README.txt'}
    members={'SD_ROOT/GXRCE.DAT','SD_ROOT/README.txt','OWNER_STEPS_PROBE2.md','ramp2.html','SHA256SUMS'}
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==members and len(z.namelist())==5 and z.testzip() is None
        checks={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            value,name=line.split('  ',1);assert name not in checks;checks[name]=value
        assert set(checks)==members-{'SHA256SUMS'}
        for name,value in checks.items():
            payload=z.read(name);assert sha(payload)==value
            expected=(PACKAGE/'local'/name).read_bytes();assert payload==expected
    owner=(HERE/'OWNER_STEPS_PROBE2.md').read_text()
    sequence=re.findall(r'^\| (\d+) \| P([12]) · [^|]+ \| `([^`]+)` \| 1/15 \| 1 \|$',owner,re.M)
    names=['M26 A','P1 R-2','P1 G-2','P1 B-2','M26 A','M26 A','P2 R+2','P2 G+2','P2 B+2','P2 R+2','P2 G+2','P2 B+2','M26 A']
    assert sequence==[(str(i+1),'1' if i<5 else '2',name) for i,name in enumerate(names)]
    assert 'f/5.6' in owner and 'G154L.DAT' in owner and '刷过 v3.10 就不能用' in owner
    for path in (root/'README.txt',HERE/'ramp2.html'):
        text=path.read_text();assert 'v3.9' in text and 'v3.10' in text
    private=[p for directory in (HERE/'local',PACKAGE/'local') for p in directory.rglob('*') if p.is_file()]
    relative=[str(p.relative_to(ROOT)) for p in private]
    command=['git','-c','core.fsmonitor=false','check-ignore','--stdin']
    proc=subprocess.run(command,input='\n'.join(relative)+'\n',text=True,capture_output=True,
        cwd=ROOT,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),timeout=120)
    assert proc.returncode==0 and set(proc.stdout.splitlines())==set(relative),'private file not ignored'
    for p in HERE.rglob('*'):
        if p.is_file() and 'local' not in p.relative_to(HERE).parts:
            assert p.suffix.lower() not in {'.dat','.elf','.bin','.img','.dng','.jpg','.png','.map','.z'}
    result=dict(status='PASS',dat_sha256=manifest['dat_sha256'],archive_sha256=manifest['archive_sha256'],
        independent_zip_members=5,owner_rows=13,owner_sequence_correct=True,all_private_files_ignored=len(private),
        sd_root_exact=True,v39_only=True,v310_compatible=False)
    save(HERE/'evidence/delivery.json',result)
    print(json.dumps(result))


def cleanup():
    assert TMP==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/probe-pack-r2')
    assert TMP.exists() and not TMP.is_symlink() and TMP.resolve()==TMP
    rows=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,command='],text=True).splitlines()
    own={os.getpid(),os.getppid()};active=[]
    for line in rows:
        pid,ppid,command=line.strip().split(None,2)
        if int(pid) in own:continue
        if str(TMP) in command or ('probe_pack_r2/' in command and re.search(r'(python|node)\S*\s',command)):
            active.append(int(pid))
    assert not active,('task process remains',active)
    frozen=json.loads((HERE/'local/frozen-inputs.json').read_text());assert freeze()==frozen
    page=json.loads((HERE/'local/page/check.json').read_text())
    assert page['status']=='PASS' and page['closedNormally']
    paths=[p for p in TMP.rglob('*') if p.is_file()]
    size=sum(p.stat().st_size for p in paths)
    shutil.rmtree(TMP);assert not TMP.exists()
    result=dict(status='PASS',path=str(TMP),files=len(paths),bytes=size,temporary_directory_absent=True,
        active_task_processes=active,protected_input_hashes_unchanged=len(frozen),browser_closed_normally=page['closedNormally'])
    save(HERE/'local/cleanup.json',result);print(json.dumps(result))


def write_sums(path,files):
    unique=sorted(set(files))
    path.write_text(''.join(digest(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in unique))


def verify_sums(path):
    count=0
    for line in path.read_text().splitlines():
        wanted,name=line.split('  ',1);p=ROOT/name
        assert p.is_file() and digest(p)==wanted,(str(path),name)
        count+=1
    return count


def seal():
    assert not TMP.exists()
    assert (HERE/'REPORT_PROBE2.md').read_text().splitlines()[0]=='可以交复审'
    local=HERE/'local/SHA256SUMS'
    private=[p for directory in (HERE/'local',PACKAGE/'local') for p in directory.rglob('*') if p.is_file() and p!=local]
    write_sums(local,private)
    files=[p for p in HERE.rglob('*') if p.is_file() and 'local' not in p.relative_to(HERE).parts and p.name!='SHA256SUMS']
    files += [local,PACKAGE/'SHA256SUMS',PACKAGE/'README.md',PACKAGE/'MANIFEST.json']
    write_sums(HERE/'SHA256SUMS',files)
    verify()


def verify():
    assert not TMP.exists()
    sums=[HERE/'SHA256SUMS',HERE/'local/SHA256SUMS',PACKAGE/'SHA256SUMS']
    results={str(p.relative_to(ROOT)):verify_sums(p) for p in sums}
    assert freeze()==json.loads((HERE/'local/frozen-inputs.json').read_text())
    print(json.dumps(dict(status='PASS',verified_checksums=results,temporary_directory_absent=True)))


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['package','cleanup','seal','verify']);args=p.parse_args()
    guard(create_tmp=False);assert os.getpriority(os.PRIO_PROCESS,0)>=10
    {'package':package_check,'cleanup':cleanup,'seal':seal,'verify':verify}[args.stage]()


if __name__=='__main__':main()
