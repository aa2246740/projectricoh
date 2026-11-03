#!/usr/bin/python3
"""Rebuild a frozen profile after checking the disk and original inputs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')


def preflight():
    subprocess.run(['/bin/df','-h','/Volumes/Workspace'],check=True)
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
    assert info['WritableVolume'] and info['WritableMedia']
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    receipt=json.loads((HERE/'input_receipt.json').read_text())
    for name,value in receipt.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value['sha256'],name
    tools=json.loads((HERE/'options/baseline/inputs.json').read_text())
    for name,value in tools.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,name
    TEMP.mkdir(parents=True,exist_ok=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',default='neutral')
    p.add_argument('--all',action='store_true');args=p.parse_args()
    profiles=json.loads((HERE/'profiles.json').read_text())
    names=list(profiles)if args.all else [args.profile]
    assert all(name in profiles for name in names)
    preflight()
    spec=importlib.util.spec_from_file_location('window_measure',HERE/'measure.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    for name in names:
        profile=profiles[name];result=mod.build(name,profile['cuts'],profile['flags'])
        if name=='neutral_plus768':assert not result.get('link_ok',False)
        else:assert result.get('link_ok',False),result


if __name__=='__main__':main()
