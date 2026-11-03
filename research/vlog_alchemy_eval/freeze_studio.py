"""Freeze the current Studio source for a bounded repeat after concurrent edits."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,SCRATCH,STUDIO_SNAPSHOT,digest,dump,result_path
setup()
import json
import shutil
from datetime import datetime,timezone

def source_files(base):
    return {p.relative_to(base).as_posix():digest(p) for p in sorted(base.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def main():
    if STUDIO_SNAPSHOT.exists():
        raise ValueError('Source snapshot already exists')
    source=ROOT/'studio/src'
    before=source_files(source)
    shutil.copytree(source,STUDIO_SNAPSHOT/'src',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    copied=source_files(STUDIO_SNAPSHOT/'src')
    after=source_files(source)
    if before!=copied or before!=after:
        raise ValueError('Studio source changed while copying')
    baseline=SCRATCH/'result_baseline'
    baseline.mkdir()
    names=['fuji_accuracy.json','look_fits.json','all_fit_parameters.json','lumix_fit_parameters.json',
           'studio_imports.json','creator_input_checks.json','hasselblad_checks.json','studio_photo_checks.json',
           'build_parameter_checks.json','physical_ring_checks.json']
    for name in names:
        shutil.copyfile(result_path(name),baseline/name)
    dump('studio_snapshot_receipt.json',{'created_utc':datetime.now(timezone.utc).isoformat(),
         'source':str(source),'temporary_snapshot':str(STUDIO_SNAPSHOT),'files':copied,
         'source_unchanged_during_copy':True,'snapshot_will_be_removed':True,
         'repeat_outputs':names,
         'repeat_output_paths':{name:str(result_path(name).relative_to(ROOT)) for name in names}})
    sys.path.insert(0,str(STUDIO_SNAPSHOT/'src'))
    from data import scenes
    ss=scenes()
    print('Frozen Studio files',len(copied),'prepared scenes',len(ss),flush=True)

if __name__=='__main__':
    main()
