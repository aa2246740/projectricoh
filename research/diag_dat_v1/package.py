"""Assemble exactly the 30-file gen120b package, replacing only GXRCE.DAT."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope import *


def main():
    freeze_check()
    source=ROOT/'firmware/package_v36_g120b/SD_ROOT'
    dest=PACKAGE/'local/SD_ROOT';dest.mkdir(parents=True,exist_ok=True)
    names=sorted(p.name for p in source.iterdir() if p.is_file())
    assert len(names)==30 and len(list(source.iterdir()))==30
    dat=ENGINE/'candidate/local/full-r13/GXRCE.DAT'
    assert int.from_bytes(dat.read_bytes()[28:32],'big')==125
    files=[]
    for name in names:
        old=source/name;src=dat if name=='GXRCE.DAT' else old
        shutil.copyfile(src,dest/name)
        assert sha(src)==sha(dest/name)
        files.append(dict(name=name,sha256=sha(dest/name),baseline_sha256=sha(old),changed=sha(old)!=sha(dest/name)))
    assert len(list(dest.iterdir()))==30 and [f['name'] for f in files if f['changed']]==['GXRCE.DAT']
    assert (dest/'GXRCE.DAT').read_bytes()==dat.read_bytes()
    save(PACKAGE/'manifest.json',dict(generation=125,status='HOST_REVIEW_CANDIDATE',files=files,
        dat_sha256=sha(dat),fixed_files_identical=29,camera_acceptance='NOT_RUN'))
    save(OUT/'evidence/package.json',dict(status='PASS',generation=125,dat_sha256=sha(dat),file_count=30,
        unchanged_fixed_files=29,changed=['GXRCE.DAT'],package=str(dest.relative_to(ROOT))))
    (PACKAGE/'CARD_SHA256SUMS').write_text(''.join(f"{f['sha256']}  {dest.relative_to(ROOT)}/{f['name']}\n" for f in files))
    print('PASS package: 30 files, 29 identical to gen120b; generation125',sha(dat))


if __name__=='__main__':main()
