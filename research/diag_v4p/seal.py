"""Hash the final delivery and receipts after temporary files are removed."""
from pathlib import Path
import json
import plistlib
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s


def main():
    sys.dont_write_bytecode=True;sys.addaudithook(s.fence)
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['FilesystemType']=='apfs' and info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['WritableVolume']
    manifest=s.HERE/'SHA256SUMS'
    files=lambda:sorted(path for base in (s.ENGINE,s.PACKAGE,s.HERE) for path in base.rglob('*') if path.is_file() and path!=manifest)
    assert {path.name for path in s.PACKAGE.iterdir()}=={'GXRCE.DAT'}
    assert not s.TMP.exists()
    assert all(not path.is_symlink() for path in files())
    s.save(s.HERE/'evidence/seal.json',dict(dat_sha256=s.sha(s.PACKAGE/'GXRCE.DAT'),temporary_tree_absent=True,
        package_files=['GXRCE.DAT'],roots=[str(path) for path in (s.ENGINE,s.PACKAGE,s.HERE)]))
    paths=files();manifest.write_text(''.join(s.sha(path)+'  '+str(path.relative_to(s.ROOT))+'\n' for path in paths))
    print(json.dumps(dict(files=len(paths),manifest_sha256=s.sha(manifest),dat_sha256=s.sha(s.PACKAGE/'GXRCE.DAT'))))


if __name__=='__main__':main()
