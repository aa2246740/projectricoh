#!/usr/bin/python3
"""Read-only verification of the sealed body packages and evidence inventory."""
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASES=(HERE,ROOT/'firmware/image_v310',ROOT/'firmware/package_v310_g155',
       ROOT/'firmware/package_v310_g155_test')
IMAGE_SHA='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
ZIP_SHA='3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sums(manifest,expected):
    seen=set()
    for line in manifest.read_text().splitlines():
        expected_hash,name=line.split('  ',1)
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(),name
        assert path not in seen,name
        assert digest(path)==expected_hash,name
        seen.add(path)
    assert seen==expected,(sorted(str(p) for p in expected-seen),
                           sorted(str(p) for p in seen-expected))
    return len(seen)


def main():
    volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType']=='apfs' and volume['Writable']
    expected={p.resolve() for base in BASES for p in base.rglob('*') if p.is_file()
              and p not in (HERE/'SHA256SUMS',HERE/'SHA256SUMS.partial')}
    checked=verify_sums(HERE/'SHA256SUMS',expected)
    for base in BASES[1:]:
        verify_sums(base/'SHA256SUMS',{p.resolve() for p in base.rglob('*')
                    if p.is_file() and p.name!='SHA256SUMS'})
    archive=ROOT/'artifacts/downloads/gxr-151.zip'
    assert digest(archive)==ZIP_SHA
    with zipfile.ZipFile(archive) as stream:
        official={Path(row.filename).name:stream.read(row) for row in stream.infolist() if not row.is_dir()}
    assert len(official)==29
    assert digest(ROOT/'firmware/image_v310/local/ilaunch3')==IMAGE_SHA
    for suffix in ('','_test'):
        package=ROOT/('firmware/package_v310_g155'+suffix)
        sd=package/'local/SD_ROOT'
        assert {p.name for p in sd.iterdir()}==set(official)|{'GXRCE.DAT'}
        assert digest(sd/'ilaunch3')==IMAGE_SHA
        assert (sd/'GXRCE.DAT').read_bytes()==(package/'GXRCE.DAT').read_bytes()
        for name,data in official.items():
            if name!='ilaunch3':assert (sd/name).read_bytes()==data,name
        manifest=json.loads((package/'MANIFEST').read_text())
        assert manifest['body_image_sha256']==IMAGE_SHA
        assert manifest['dat_sha256']==digest(sd/'GXRCE.DAT')
        assert manifest['verdict']=='有缺陷' and manifest['acceptance']=='defects'
        assert not manifest['camera_verified']
    report=HERE/'REPORT.md'
    assert report.read_text().splitlines()[0]=='有缺陷'
    for doc in (report,HERE/'OWNER_STEPS.md',ROOT/'firmware/image_v310/README.md'):
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',doc.read_text()):
            if '://' not in target:
                assert (doc.parent/target.split('#')[0]).resolve().exists(),target
    scripts=[p for base in BASES for p in base.rglob('*.py')]
    for script in scripts:compile(script.read_bytes(),str(script),'exec')
    acceptance=json.loads((HERE/'evidence/acceptance.json').read_text())
    assert acceptance['identity']['passed']==21
    assert acceptance['valid_records']['passed']==0 and acceptance['valid_records']['failed']==5
    assert acceptance['recovery']['full_restore']=='INCOMPLETE'
    assert acceptance['recovery']['final_image_equality']=='OPEN'
    cleanup=json.loads((HERE/'evidence/cleanup.json').read_text())
    assert cleanup['deleted'] and not Path(cleanup['temporary']).exists()
    assert cleanup['protected_input_changes']==0 and cleanup['residual_test_processes']==[]
    frozen=json.loads((HERE/'evidence/frozen-verification.json').read_text())
    assert frozen['files']==14966 and frozen['changed']==[]
    wording=json.loads((HERE/'evidence/wording-check.json').read_text())
    assert wording['matches']==[]
    sys.path.insert(0,str(HERE))
    from launch import active
    assert active()==[]
    print(json.dumps(dict(verdict='有缺陷',verified_files=checked,compiled_scripts=len(scripts),
        official_companions_per_package=28,package_files_per_SD_ROOT=30,
        image_sha256=IMAGE_SHA,temporary_deleted=True,residual_tests=0),ensure_ascii=False))


if __name__=='__main__':main()
