"""Isolate the R3 repairs; preserve every previous candidate and receipt."""
import datetime,hashlib,json,os,plistlib,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OLD=ROOT/'tools/gxr_emulator_fast/strict_r2';NEW=ROOT/'tools/gxr_emulator_fast/strict_r3'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-fix-r1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    disk=plistlib.loads(subprocess.run(['diskutil','info','-plist','/Volumes/Workspace'],capture_output=True,check=True,timeout=20).stdout)
    assert disk['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and disk['FilesystemType']=='apfs' and disk['WritableVolume']
    assert not NEW.exists() and not TEMP.exists()
    for n in ('scripts','runs','local','prior'):(HERE/n).mkdir(exist_ok=True)
    TEMP.mkdir(parents=True)
    files=[p for p in OLD.iterdir() if p.is_file()]
    files += [p for p in (OLD/'build').iterdir() if p.is_file() and p.suffix in ('.json','.so','.dylib')]
    for base in ('tools/gxr_emulator_fast','tools/gxr_emulator_fast/fix_r1'):
        files += [p for p in (ROOT/base).iterdir() if p.is_file()]
    record=dict(status='PASS',started=datetime.datetime.now(datetime.timezone.utc).isoformat(),deadline='2026-11-03T17:16:06+00:00',
        previous_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},
        review_sha256=sha(ROOT/'research/review_emulator_fast_r3/REVIEW.md'),volume_uuid=disk['VolumeUUID'],load=os.getloadavg())
    for name in ('REPORT.md','PROGRESS.md','SHA256SUMS'):
        shutil.copy2(HERE.parent/name,HERE/'prior'/name)
    NEW.mkdir()
    for path in OLD.iterdir():
        if path.is_file() and path.name!='SHA256SUMS':shutil.copy2(path,NEW/path.name)
    shutil.copytree(OLD/'build',NEW/'build')
    for path in (HERE.parent/'strict_r2/scripts').glob('*.py'):
        (HERE/'scripts'/path.name).write_text(path.read_text().replace('strict_r2','strict_r3'))
    (HERE/'runs/initial-freeze.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',candidate=str(NEW),frozen=len(record['previous_files']))))
if __name__=='__main__':main()
