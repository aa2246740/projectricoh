"""Verify and hash the final review files without recreating task scratch."""
import json
from pathlib import Path
import runpy
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def verify_sums(path):
    count=0
    for line in path.read_text().splitlines():
        expected,name=line.split('  ',1)
        target=ROOT/name
        assert target.resolve().is_relative_to(ROOT)
        assert not target.is_symlink()
        assert sha(target.read_bytes())==expected,(name,'checksum mismatch')
        count+=1
    return count


def main():
    guard(create_tmp=False)
    assert not TMP.exists()
    assert freeze()==json.loads((HERE/'local/frozen-inputs.json').read_text())
    for name in ('acceptance','cleanup','reproduce','page','python'):
        assert json.loads((HERE/'evidence'/f'{name}.json').read_text())['status']=='PASS'
    archive=PACKAGE/'local/GXR-probe-r1.zip'
    previous=archive.read_bytes()
    runpy.run_path(str(HERE/'package.py'),run_name='__main__')
    assert archive.read_bytes()==previous,'archive reproduction changed bytes'
    manifest=json.loads((PACKAGE/'MANIFEST.json').read_text())
    assert manifest['archive_sha256']==sha(previous)
    assert {p.name for p in (PACKAGE/'local/SD_ROOT').iterdir()}=={'GXRCE.DAT','README.txt'}
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())=={'SD_ROOT/GXRCE.DAT','SD_ROOT/README.txt',
                                 'OWNER_STEPS.md','patches.html','SHA256SUMS'}
        assert z.testzip() is None
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            assert sha(z.read(name))==digest
        for name in ('OWNER_STEPS.md','patches.html'):
            assert z.read(name)==(HERE/name).read_bytes()
        assert z.read('SD_ROOT/GXRCE.DAT')==(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    package_count=verify_sums(PACKAGE/'SHA256SUMS')
    local_sum=HERE/'local/SHA256SUMS'
    private=sorted(p for folder in (HERE/'local',PACKAGE/'local') for p in folder.rglob('*')
                   if p.is_file() and p!=local_sum)
    assert all(not p.is_symlink() for p in private)
    local_sum.write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in private))
    local_count=verify_sums(local_sum)
    excluded={HERE/'SHA256SUMS',HERE/'evidence/seal.json'}
    public=sorted({p for p in HERE.rglob('*') if p.is_file() and p not in excluded
                   and 'local' not in p.relative_to(HERE).parts}
                  |{local_sum,PACKAGE/'MANIFEST.json',PACKAGE/'SHA256SUMS'})
    (HERE/'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in public))
    public_count=verify_sums(HERE/'SHA256SUMS')
    assert not TMP.exists()
    result=dict(status='PASS',dat_sha256=manifest['dat_sha256'],
        archive_sha256=manifest['archive_sha256'],archive_byte_identical_reproduction=True,
        public_files=public_count,private_files=local_count,package_files=package_count,
        public_manifest_sha256=sha((HERE/'SHA256SUMS').read_bytes()),
        private_manifest_sha256=sha(local_sum.read_bytes()),
        manifest_exclusions=['each checksum manifest excludes itself','evidence/seal.json avoids a checksum cycle'],
        temporary_directory_absent=True,protected_inputs_unchanged=len(freeze()))
    save(HERE/'evidence/seal.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
