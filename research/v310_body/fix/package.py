#!/usr/bin/python3
"""Package new DAT files with the frozen v3.10 body and official companions."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType']=='apfs' and volume['Writable']
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    archive=ROOT/'artifacts/downloads/gxr-151.zip'
    archive_sha=sha(archive.read_bytes())
    assert archive_sha=='3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
    with zipfile.ZipFile(archive) as stream:
        official={Path(row.filename).name:stream.read(row) for row in stream.infolist() if not row.is_dir()}
    assert len(official)==29
    body=(ROOT/'firmware/image_v310/local/ilaunch3').read_bytes()
    assert sha(body)=='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
    result=[]
    for suffix in ('','_test'):
        package=ROOT/('firmware/package_v310_g155b'+suffix)
        sd=package/'local/SD_ROOT';sd.mkdir(parents=True,exist_ok=True)
        dat=(package/'GXRCE.DAT').read_bytes()
        manifest=json.loads((package/'MANIFEST').read_text())
        assert sha(dat)==manifest['dat_sha256']
        for name,data in official.items():(sd/name).write_bytes(body if name=='ilaunch3' else data)
        (sd/'GXRCE.DAT').write_bytes(dat)
        assert len(list(sd.iterdir()))==30
        files=[]
        for path in sorted(sd.iterdir()):
            data=path.read_bytes()
            if path.name not in ('ilaunch3','GXRCE.DAT'):assert data==official[path.name]
            files.append(dict(name=path.name,bytes=len(data),sha256=sha(data)))
        for name in ('FOTUFILM-NOTICE.txt','FILM-PROFILES-NOTICE.txt','LICENSE-CC-BY-SA-4.0.txt'):
            (package/name).write_bytes((ROOT/'firmware/package_v310_g155'/name).read_bytes())
        manifest.update(body_image_built=True,body_image_sha256=sha(body),generation=155,
            format_changed=False,official_companions=28,official_zip_sha256=archive_sha,
            camera_verified=False,acceptance='pending',files=files,
            source_engine='firmware/engine_v66_g155b',source_body='firmware/image_v310/local/ilaunch3')
        (package/'MANIFEST').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        result.append(dict(package=str(package.relative_to(ROOT)),dat_sha256=sha(dat),files=files))
    (HERE/'evidence/packages.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(package=r['package'],dat_sha256=r['dat_sha256'],files=len(r['files'])) for r in result]))


if __name__=='__main__':main()
