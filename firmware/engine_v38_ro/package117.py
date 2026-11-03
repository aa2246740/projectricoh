"""Build and independently verify the 30-file gen117 SD_ROOT, without card access."""
from pathlib import Path
import hashlib,json,shutil,zipfile,sys,struct
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PACKAGE=ROOT/'firmware/package_v35_g117';SD=PACKAGE/'SD_ROOT'
ZIP=ROOT/'artifacts/downloads/gxr-151.zip'
ZIP_SHA='3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
BODY=ROOT/'firmware/image_v35/local/package/SD_ROOT/ilaunch3'
BODY_SHA='6e9ea05868b2bb56fb60de0e8506aad7b952715c061009b2acc891b45d220b20'
DAT=HERE/'candidate/local/full-r13/GXRCE.DAT'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def official():
 assert sha(ZIP)==ZIP_SHA
 with zipfile.ZipFile(ZIP) as z:rows={Path(i.filename).name:z.read(i) for i in z.infolist() if not i.is_dir()}
 assert len(rows)==29 and 'ilaunch3' in rows
 assert hashlib.sha256(rows['ilaunch3']).hexdigest()=='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
 del rows['ilaunch3'];assert len(rows)==28
 for name,raw in rows.items():assert (ROOT/'artifacts/firmware/gxr-1.51'/name).read_bytes()==raw
 return rows
def prepare():
 rows=official();assert sha(BODY)==BODY_SHA
 assert struct.unpack_from('>I',DAT.read_bytes(),28)[0]==117
 SD.mkdir(exist_ok=True)
 assert all(p.is_file() and p.name in {*rows,'ilaunch3','GXRCE.DAT'} and not p.is_symlink() for p in SD.iterdir())
 for name,raw in rows.items():(SD/name).write_bytes(raw)
 shutil.copyfile(BODY,SD/'ilaunch3');shutil.copyfile(DAT,SD/'GXRCE.DAT')
 return verify()
def verify():
 rows=official();files=list(SD.iterdir());assert len(files)==30 and all(p.is_file() and not p.is_symlink() for p in files)
 assert {p.name for p in files}=={*rows,'ilaunch3','GXRCE.DAT'}
 assert sha(SD/'ilaunch3')==BODY_SHA and (SD/'GXRCE.DAT').read_bytes()==DAT.read_bytes()
 for name,raw in rows.items():assert (SD/name).read_bytes()==raw
 result=dict(status='PASS',files=30,official_files_equal_zip=28,zip_sha256=ZIP_SHA,ilaunch3_sha256=BODY_SHA,generation=117,dat_sha256=sha(DAT),dat_bytes=DAT.stat().st_size)
 (HERE/'local/package-verification.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS SD_ROOT: exactly 30 files; official=28 byte-identical; body='+BODY_SHA+'; gen117='+sha(DAT))
 return result
def sums():
 assert (PACKAGE/'REPORT.md').is_file();verify()
 paths=sorted(p for p in PACKAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
 (PACKAGE/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(PACKAGE).as_posix()+'\n' for p in paths))
 print('PASS dir-relative SHA256SUMS entries',len(paths))
if __name__=='__main__':
 if '--sums' in sys.argv:sums()
 elif '--verify' in sys.argv:verify()
 else:prepare()
