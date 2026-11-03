"""Run a review command with isolated paths and the resource limits."""
import json,os,sys
from pathlib import Path
base=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4')
env=json.loads((base/'environment.json').read_text())
os.environ.update(env)
os.setpriority(os.PRIO_PROCESS,0,max(10,os.getpriority(os.PRIO_PROCESS,0)))
os.chdir(base/'source')
os.execvpe(sys.argv[1],sys.argv[1:],os.environ)
