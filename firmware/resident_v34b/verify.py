"""Run v3.4b host gates; no hardware interaction or staging."""
from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
if __name__=='__main__':
    tmp=HERE/'local/runner-tmp';tmp.mkdir(parents=True,exist_ok=True)
    jobs=[('resident/verify.py',),('machine_checks.py',),('entry_machine.py',),
        ('evidence_v34b.py','body'),('evidence_v34b.py','constructor'),('evidence_v34b.py','loader'),('evidence_v34b.py','stack')]
    jobs += [('acceptance/verify_v34b.py',phase) for phase in ('compile','vectors','basic','ctl','quarantine','conflict','accepted-f02','irom','first','t','rpc-faults','blackbox','legacy','store-fault','service-quarantine','log-fault','neighbour','iso','publish-failure')]
    for script,*args in jobs:
        print('RUN',script,*args,flush=True)
        subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/script),*args],cwd=ROOT,
            env=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'),check=True)
