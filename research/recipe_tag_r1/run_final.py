"""Sequential, bounded evidence runner. At most one direct child runs at a time.

Does not build a DAT or body image, invoke Git, or open an owner Studio path.
All child scripts enforce their own read/write fences. Compiler children keep
the process tree within three processes, including this runner.
"""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-tag-r1')
info=subprocess.run(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace'],check=True,capture_output=True,timeout=20)
volume=plistlib.loads(info.stdout)
assert volume['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert volume['FilesystemType']=='apfs' and volume['WritableVolume'] and Path('/Volumes/Workspace').is_mount()
assert not TMP.is_symlink()
TMP.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,TMPDIR=str(TMP),PYTHONDONTWRITEBYTECODE='1',GXR_HARNESS_BACKEND='c',GXR_EMULATOR_BATCH='1',
         OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',MKL_NUM_THREADS='1')
system='/usr/bin/python3'
studio=str(ROOT/'studio/.venv/bin/python')
prefix='research/recipe_tag_r1/'
gcc='research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
jobs=[
    ('encoder-target-object',[gcc,'-m32r','-Os','-ffreestanding','-fno-builtin','-fPIC','-fstack-usage','-c',prefix+'tag_encoder.c','-o',str(TMP/'tag_encoder.o')],60,{}),
    ('encoder-host-library',['/usr/bin/clang','-Os','-fPIC','-dynamiclib',prefix+'tag_encoder.c','-o',str(TMP/'libtag_encoder.dylib')],60,{}),
]
for name,python,script,limit,extra in [
    ('encoder-size',system,'measure_encoder.py',60,{}),
    ('encoder-host',studio,'check_encoder.py',120,{}),
    ('static',system,'static_evidence.py',120,{}),
    ('metadata',studio,'metadata.py',120,{}),
    ('native-metadata-c',system,'native_metadata.py',120,{}),
    ('native-metadata-python',system,'native_metadata.py',120,{'GXR_HARNESS_BACKEND':'python'}),
    ('log-wrapper-c',system,'log_wrapper.py',120,{}),
    ('log-wrapper-python',system,'log_wrapper.py',120,{'GXR_HARNESS_BACKEND':'python'}),
    ('log-matching',system,'log_match.py',60,{}),
    ('inference',studio,'infer.py',600,{}),
    ('candidate-equality',studio,'candidate_equality.py',120,{}),
    ('inference-limits',studio,'inference_limits.py',180,{}),
    ('jpg-only',studio,'jpg_only.py',120,{}),
    ('visual',system,'render_results.py',60,{}),
]:jobs.append((name,[python,'-I','-B',prefix+script],limit,extra))
jobs.append(('native-log-rewrite',[system,'-I','-B',prefix+'native_log.py','--strategy','rewrite'],360,{}))
jobs.append(('native-log-direct',[system,'-I','-B',prefix+'native_log.py','--strategy','direct'],360,{}))


def main():
    rows=[];started=time.monotonic()
    for name,argv,limit,extra in jobs:
        print('START',name,flush=True);t=time.monotonic()
        result=subprocess.run(argv,cwd=ROOT,env={**env,**extra},capture_output=True,text=True,timeout=limit)
        (HERE/('final-'+name+'.log')).write_text(result.stdout+result.stderr)
        row=dict(name=name,argv=argv,exit_code=result.returncode,timeout_seconds=limit,elapsed_seconds=round(time.monotonic()-t,3))
        rows.append(row)
        (HERE/'final_run.json').write_text(json.dumps(dict(status='RUNNING' if result.returncode==0 else 'FAIL',jobs=rows),indent=2)+'\n')
        print('END',name,result.returncode,flush=True)
        if result.returncode:raise RuntimeError(name+' failed; see final-'+name+'.log')
    (HERE/'final_run.json').write_text(json.dumps(dict(status='PASS',jobs=rows,elapsed_seconds=round(time.monotonic()-started,3),
             volume_uuid=volume['VolumeUUID'],max_direct_children=1,scope='research only; no camera package'),indent=2)+'\n')


if __name__=='__main__':main()
