"""Append a prepared 48-case replay matrix to the running finite scheduler."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();p=argparse.ArgumentParser();p.add_argument('--dataset',required=True,choices=('model','control'));a=p.parse_args()
tag='r2' if a.dataset=='model' else 'r1'
q=C.LOCAL/('persistence-'+tag+'-'+a.dataset)/'replays.queue.json'
rows=json.loads(q.read_text());assert len(rows)==48
file=C.LOCAL/'r1-work.json';tasks=json.loads(file.read_text());known={t['id'] for t in tasks}
for row in rows:
    if row['label'] not in known:tasks.append(dict(id=row['label'],script='run.py',args=row['args'],log=row['log']))
key=a.dataset+'-S48-verification'
if key not in known:tasks.append(dict(id=key,script='replay.py',args=['--dataset',a.dataset,'--tag',tag,'--verify'],needs=[r['label'] for r in rows],log=str(C.LOCAL/'logs'/(key+'.log'))))
if a.dataset=='model':
    # Complete the final-record matrix before spending the remaining window
    # on the archived-data comparison. No case is removed.
    target={r['label'] for r in rows}|{key}
    insertion=next((i for i,t in enumerate(tasks) if not ('model' in t['id'] or t['id'].startswith(('link-','byte-audit','publish-','diagnostic-')) or t['id']=='boot-fixtures')),len(tasks))
    replay_tasks=[t for t in tasks if t['id'] in target]
    tasks=[t for t in tasks if t['id'] not in target]
    tasks[insertion:insertion]=replay_tasks
tmp=file.with_suffix('.tmp');C.save(tmp,tasks);tmp.replace(file)
print(json.dumps(dict(status='PASS',added_matrix=a.dataset,cases=48)))
