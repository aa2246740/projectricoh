from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('prepare-S48')
C.run([sys.executable,'-I','-B',C.HERE/'replay.py','--dataset','model','--tag','r1','--prepare-replays'],'prepare-S48')
path=C.HERE/'jobs.json';jobs=json.loads(path.read_text());known={r['id'] for r in jobs};rows=json.loads((C.LOCAL/'persistence-r1-model/replays.queue.json').read_text())
for row in rows:
    if row['label'] not in known:jobs.append(dict(id=row['label'],script='research/g158/run.py',args=[*row['args'],'--dial','AUTO'],needs=[],log=str(C.LOCAL/'logs'/(row['label']+'.log'))))
jobs.append(dict(id='verify-S48',script='research/g158/replay.py',args=['--dataset','model','--tag','r1','--verify'],needs=[r['label'] for r in rows],log=str(C.LOCAL/'logs/verify-S48.log')))
C.save(path,jobs);print(json.dumps(dict(status='PREPARED',replays=len(rows))))
