#!/usr/bin/env python3
"""Rebuild only this resident, one service library and six local containers."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--only',choices=('resident','product','probes'))
    args=p.parse_args()
    jobs={'resident':HERE/'resident/build.py','product':HERE/'containers/product/candidates.py',
          'probes':HERE/'containers/probes/build.py'}
    for name,script in jobs.items():
        if args.only and name!=args.only:continue
        subprocess.run(['/usr/bin/python3','-I','-B',str(script)],cwd=ROOT,check=True)
    if not args.only:
        subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/'audit.py')],cwd=ROOT,check=True)

if __name__=='__main__':main()
