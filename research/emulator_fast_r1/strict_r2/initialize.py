"""Create an isolated strict candidate and pin the previous delivery."""
import datetime,hashlib,json,os,plistlib,shutil,signal,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=ROOT/'tools/gxr_emulator_fast/fix_r1'
NEW=ROOT/'tools/gxr_emulator_fast/strict_r2'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-fix-r1')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def main():
    signal.alarm(300)
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    disk=plistlib.loads(subprocess.run(['diskutil','info','-plist','/Volumes/Workspace'],capture_output=True,check=True,timeout=20).stdout)
    assert disk['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType']=='apfs' and disk['WritableVolume']
    assert not NEW.exists() and not TEMP.exists()
    for name in ('runs','local','prior','scripts'):(HERE/name).mkdir(exist_ok=True)
    TEMP.mkdir(parents=True)
    rows=[]
    for base in (ROOT/'tools/gxr_emulator_fast',OLD):
        rows += [dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(base.iterdir()) if p.is_file()]
    rows += [dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted((OLD/'build').glob('*')) if p.is_file() and p.suffix in ('.so','.dylib','.json')]
    for name in ('REPORT.md','SHA256SUMS','PROGRESS.md'):
        path=HERE.parent/name
        shutil.copy2(path,HERE/'prior'/name)
    NEW.mkdir()
    for path in OLD.iterdir():
        if path.is_file():shutil.copy2(path,NEW/path.name)
    shutil.copytree(OLD/'build',NEW/'build')
    for name in ('SHA256SUMS',):
        (NEW/name).unlink()
    record=dict(status='PASS',when=datetime.datetime.now(datetime.timezone.utc).isoformat(),volume_uuid=disk['VolumeUUID'],
                candidate=str(NEW.relative_to(ROOT)),scratch=str(TEMP),previous_files=rows,
                load=os.getloadavg(),processes=subprocess.run(['ps','-axo','pid,ppid,ni,etime,command'],capture_output=True,text=True,check=True,timeout=10).stdout)
    (HERE/'runs/environment.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',pinned=len(rows),candidate=str(NEW))))

if __name__=='__main__':main()
