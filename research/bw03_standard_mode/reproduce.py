"""Reproduce the scoped offline research package with installed host tools."""
import subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
for interpreter,script,extra in (
    ('/usr/bin/python3','inspect_pipeline.py',[]),
    ('/usr/bin/python3','check_static.py',[]),
    ('/usr/bin/python3','build_candidates.py',[]),
    ('/opt/homebrew/bin/python3','predict_photos.py',[]),
    ('/opt/homebrew/bin/python3','check_branches.py',[]),
    ('/opt/homebrew/bin/python3','verify.py',['--write']),
    ('/opt/homebrew/bin/python3','finish.py',[]),
    ('/opt/homebrew/bin/python3','verify.py',['--hashes'])):
    subprocess.run([interpreter,'-I','-B',str(HERE/script),*extra],cwd=ROOT,check=True)
