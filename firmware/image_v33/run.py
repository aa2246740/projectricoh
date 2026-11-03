"""Copied image-v3 build/audit/negative checks for the new resident only."""
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
RESIDENT=ROOT/'firmware/resident_v33/local'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('build','audit','verify'));args=parser.parse_args()
    (LOCAL/'tmp').mkdir(parents=True,exist_ok=True)
    common=['--elf',RESIDENT/'resident/build/resident.elf','--hooks',RESIDENT/'hooks.json',
            '--patch-manifest',RESIDENT/'resident/patch-manifest.json']
    package=LOCAL/'candidate-v33'
    if args.phase=='build':
        command=['--official',ROOT/'artifacts/firmware/gxr-1.51/ilaunch3',*common,'--output',package]
    elif args.phase=='audit':
        command=['--package',package,*common,'--official',ROOT/'artifacts/firmware/gxr-1.51/ilaunch3']
    else:
        command=['--package',package,*common,'--output',LOCAL/'verification']
    env=dict(os.environ,TMPDIR=str(LOCAL/'tmp'),PYTHONDONTWRITEBYTECODE='1')
    argv=['/usr/bin/python3','-I','-B',HERE/(args.phase+'.py'),*command]
    result=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,text=True,capture_output=True)
    (LOCAL/(args.phase+'.log')).write_text(result.stdout+result.stderr)
    (LOCAL/(args.phase+'-command.json')).write_text(json.dumps(list(map(str,argv)),indent=2)+'\n')
    print(result.stdout+result.stderr,end='')
    if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
