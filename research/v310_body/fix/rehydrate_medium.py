#!/usr/bin/python3
"""Copy the exact retained medium required by one actual execution snapshot."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import plistlib
import shutil
import subprocess
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',type=Path,required=True);a=p.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    assert a.snapshot.resolve().is_relative_to(HERE/'local')
    subprocess.run(['/bin/df','-h','/Volumes/Workspace'],check=True)
    volume=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert volume['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['FilesystemType']=='apfs' and volume['WritableVolume']
    sys.path.insert(0,str(ROOT/'tools/gxr_emulator_standby'))
    for name,file_name in (('v310_preview_link','preview_link.py'),('v310_word_nand','nand_word.py')):
        spec=importlib.util.spec_from_file_location(name,HERE/'emulator'/file_name)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    state=pickle.loads(zlib.decompress(a.snapshot.read_bytes()))['cpu']
    sd=next(d for t,d in zip(state['device_types'],state['devices']) if t=='SdHost')
    record=sd['medium_record'];target=Path(record['path'])
    assert target.resolve().is_relative_to(TEMP)
    source=HERE/'local/media'/(record['sha256']+'.img')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==record['sha256']
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']
    else:shutil.copyfile(source,target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']
    print(json.dumps(dict(snapshot=str(a.snapshot),medium=str(target),sha256=record['sha256'],native_state_presets=[])))


if __name__=='__main__':main()
