"""List full-review commands still lacking final-artifact completion evidence."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,DAT,save,file_sha
from run_queue import commands

def read(path):
    if not path.exists():return None
    try:return json.loads(path.read_text())
    except json.JSONDecodeError:return None

digest=file_sha(DAT);rows=[]
for command in commands():
    unit=next(x for x in command if x in ('50mm','28mm','mount'))
    proof=None;status='INCOMPLETE'
    if command[0]=='fn2_all.py':proof='native/fn2-four-parameters-'+unit+'.json'
    elif command[:2]==('run_native.py','matrix'):proof='native/matrix-'+unit+'.json'
    elif command[:2]==('fn2_quality.py','measure'):proof='native/fn2-step-counts-'+unit+'.json'
    if proof:
        x=read(OUT/proof) or {}
        bound=x.get('dat_sha256') or x.get('dat')
        if bound==digest and x.get('status')=='PASS':status='PASS'
    else:
        x=read(OUT/('remaining-'+unit+'.json')) or {}
        found=next((r for r in x.get('commands',[]) if tuple(r['command'])==tuple(command)),None)
        if found and found['returncode']==0:status='PASS';proof=found['log']
        elif found:status='FAIL';proof=found['log']
    rows.append(dict(command=['/usr/bin/python3','-I','-B','research/g121_field_fix/'+command[0],*command[1:]],status=status,proof=proof))
save('unfinished-commands.json',dict(dat_sha256=digest,expected=len(rows),completed=sum(x['status']=='PASS' for x in rows),
    commands=rows,scope='Only the original full review command set. Targeted final checks are listed separately in acceptance.json.'))
print('Full review completed',sum(x['status']=='PASS' for x in rows),'of',len(rows),flush=True)
