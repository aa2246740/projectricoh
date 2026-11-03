"""Stage and read back the complete generation 128 package."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope

def main():
    scope.freeze_check()
    base = scope.ROOT/'firmware/package_v36_g120b/SD_ROOT'
    previous = scope.ROOT/'firmware/package_v36_diag1/local/SD_ROOT'
    package = scope.ROOT/'firmware/package_v36_diag2'
    dest = package/'local/SD_ROOT'
    dest.mkdir(parents=True, exist_ok=True)
    dat = scope.ROOT/'firmware/engine_diag_v2/candidate/local/full-r13/GXRCE.DAT'
    records=[]
    for p in sorted(previous.iterdir()):
        if not p.is_file():
            raise ValueError('UNEXPECTED_PACKAGE_ENTRY')
        source=dat if p.name=='GXRCE.DAT' else p
        shutil.copyfile(source,dest/p.name)
        digest=scope.sha(dest/p.name)
        assert digest==scope.sha(source)
        if p.name!='GXRCE.DAT':
            assert digest==scope.sha(base/p.name)
        records.append(dict(name=p.name,sha256=digest,bytes=(dest/p.name).stat().st_size))
    assert len(records)==30 and len(list(dest.iterdir()))==30
    raw=dat.read_bytes()
    assert int.from_bytes(raw[28:32],'big')==128
    scope.save(package/'manifest.json',dict(generation=128,files=records,
        fixed_files_identical=29,dat_sha256=scope.sha(dat),camera_acceptance='NOT_RUN'))
    (package/'CARD_SHA256SUMS').write_text(''.join(
        x['sha256']+'  '+str((dest/x['name']).relative_to(scope.ROOT))+'\n' for x in records))
    (package/'STATUS.txt').write_text('Generation 128. Complete 30-file package. Host review candidate.\n')
    print('PACKAGE',len(records),'FIXED',29,'DAT',scope.sha(dat))

if __name__=='__main__':
    main()
