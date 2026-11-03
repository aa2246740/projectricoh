"""Run every requested gen 116 stage; preserve failures instead of skipping."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a

phases=('vectors','basic','first','blackbox','neighbour','t','iso','ctl','rpc-faults',
        'conflict','accepted-f02','same-conflict','log-fault','service-quarantine',
        'publish-failure','store-fault','daily','rejected','r33','quarantine','irom','legacy')
results=[]
for phase in phases:
    p=a.run(['/usr/bin/python3','-I','-B',a.HERE/'isolated/candidate/verify_v34c.py',phase],
            'host-stage-'+phase,timeout=600,check=False)
    row=dict(phase=phase,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode())
    results.append(row);a.dump('host-stages.json',results)
    print(phase,p.returncode,p.stdout.decode().strip()[-150:],p.stderr.decode()[-200:],flush=True)

for case in ('normal','absent','short','long','readonly','partial','duplicate','transient','persistent'):
    p=a.run([a.HERE/'fs_probe',case],'fs-'+case,check=False)
    print(p.stdout.decode(),p.stderr.decode(),end='',flush=True)
