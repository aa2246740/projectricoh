"""Assemble the unchanged v3.6 body, generation 120 recipe and official files."""
from pathlib import Path
import shutil
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, PACKAGE, file_sha, sha, save

sd = PACKAGE / 'SD_ROOT'
sd.mkdir(parents=True, exist_ok=True)
archive = ROOT / 'artifacts/downloads/gxr-151.zip'
assert file_sha(archive) == '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'
with zipfile.ZipFile(archive) as z:
    companions = []
    for item in z.infolist():
        if item.is_dir() or item.filename.startswith('__MACOSX/'):
            continue
        name, data = Path(item.filename).name, z.read(item)
        if name == 'ilaunch3':
            assert sha(data) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
        else:
            (sd / name).write_bytes(data)
            companions.append(name)
    assert len(companions) == 28
body = ROOT / 'firmware/package_v36_g119/SD_ROOT/ilaunch3'
assert file_sha(body) == '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'
shutil.copyfile(body, sd / 'ilaunch3')
shutil.copyfile(TREE / 'candidate/local/full-r13/GXRCE.DAT', sd / 'GXRCE.DAT')
assert len(list(sd.iterdir())) == 30
(PACKAGE / 'CARD_SHA256SUMS').write_text(''.join(file_sha(p) + '  SD_ROOT/' + p.name + '\n' for p in sorted(sd.iterdir())))
save('package-assembly.json', dict(status='PASS', files=30, official_companions=28,
                                   body=file_sha(body), dat=file_sha(sd / 'GXRCE.DAT')))
print('PASS package assembled; 30 files, 28 official companions', flush=True)
