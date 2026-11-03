"""Recreate isolated build caches before rerunning the recorded gates."""
from pathlib import Path
import os,plistlib,shutil,subprocess
REPORT=Path(__file__).resolve().parent
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
v=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert v['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and v['FilesystemType']=='apfs' and v['Writable']
TEMP.mkdir(parents=True,exist_ok=True)
corepack=Path(os.environ.get('COREPACK_HOME','/Users/wu/.cache/node/corepack'))
if corepack.is_dir():shutil.copytree(corepack,TEMP/'corepack',dirs_exist_ok=True)
env={**os.environ,'TMPDIR':str(TEMP)+'/', 'UV_CACHE_DIR':str(TEMP/'uv-cache'), 'COREPACK_HOME':str(TEMP/'corepack')}
subprocess.run(['uv','build','--out-dir',str(TEMP/'backend-warm-dist')],cwd=WT,env=env,check=True,timeout=600)
print('Isolated build backend and package-manager caches are ready. Existing worktree dependencies are required.')
