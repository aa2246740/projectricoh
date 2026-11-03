"""Foreground verification by default; optionally refit missing cells."""
import argparse
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--fit-missing',action='store_true')
    args=ap.parse_args()
    commands=[]
    if args.fit_missing:
        commands.extend([('run.py','preflight'),('lut_control.py',)])
        commands.extend([('run.py','fit','--slots',slot,'--nfev','40') for slot in ('05','06','01','02')])
        commands.extend([('continue_fits.py','--slot',slot) for slot in ('05','06','01','02')])
    commands.extend([('verify.py',),('diagnostics.py',),('report.py',),('seal.py',)])
    for script,*rest in commands:
        print('running',script,*rest,flush=True)
        subprocess.run([sys.executable,'-I','-B',str(HERE/script),*rest],cwd=ROOT,check=True)


if __name__=='__main__':main()
