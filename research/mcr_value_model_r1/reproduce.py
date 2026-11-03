"""Reproduce retained models and verify outputs using finite foreground commands."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
COMMANDS=[
    ['run.py','check'],
    ['run.py','fit'],
    ['run.py','aggregate'],
    ['run.py','fit','--tag','at_curve','--placement','at_curve','--hypotheses','H1,H2'],
    ['run.py','aggregate','--tag','at_curve'],
    ['look_study.py'],
    ['verify.py'],
    ['verify_look.py'],
    ['report.py'],
    ['seal.py'],
]


def main():
    for name,*args in COMMANDS:
        subprocess.run(['python3','-I','-B',str(HERE/name),*args],cwd=ROOT,check=True)


if __name__=='__main__':main()
