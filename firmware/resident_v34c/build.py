"""Rebuild this host-only resident and generation 113 engine."""
from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
if __name__=='__main__':
    tmp=HERE/'local/runner-tmp';tmp.mkdir(parents=True,exist_ok=True)
    for script in ('resident/build.py','acceptance/build_r11.py'):
        subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/script)],cwd=ROOT,
            env=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'),check=True)
