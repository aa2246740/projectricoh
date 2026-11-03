"""Run the frozen source without local captures and without the ImageIO path."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-hdr')
MIRROR=TMP/'portable/studio'
MIRROR.mkdir(parents=True,exist_ok=True)
frozen=json.loads((OUT/'frozen_inputs.json').read_text())
count=0
for name,receipt in frozen['files'].items():
    if not name.startswith('studio/') or name.startswith('studio/.git/'):
        continue
    source=ROOT/name
    dest=MIRROR/name[len('studio/'):]
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==receipt['sha256'],name
    count+=1
(MIRROR/'.git').symlink_to(ROOT/'studio/.git',target_is_directory=True)
assert not (MIRROR.parent/'captures').exists()
os.chdir(MIRROR)
sys.path[:0]=[str(MIRROR/'src'),str(MIRROR/'tests')]
import pytest

class PortableConditions:
    def pytest_configure(self,config):
        import hdr_support as hs
        import gxr_studio
        assert Path(gxr_studio.__file__).resolve().is_relative_to(MIRROR)
        hs.ON_MACOS=False
        hs.HAS_IMAGEIO=False
        hs.needs_imageio=pytest.mark.skipif(True,reason='review: ImageIO unavailable condition')
        result={'actual_kernel':os.uname().sysname,'source':gxr_studio.__file__,'source_files_identical':count,
                'real_captures_present':False,'imageio_available':hs.HAS_IMAGEIO,
                'git_root':subprocess.check_output(['git','--no-optional-locks','rev-parse','--show-toplevel'],text=True).strip()}
        (OUT/'portable_runtime.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))

code=pytest.main(['-q','--durations=10','--force-reruns','0','--cov=gxr_studio','--cov-report=term-missing','--cov-fail-under=85'],
                 plugins=[PortableConditions()])
raise SystemExit(code)
