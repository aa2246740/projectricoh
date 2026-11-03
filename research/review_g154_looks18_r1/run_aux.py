"""Serial identity, recovery and paired C/Python inherited-OPEN checks."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_checks import run

def checked(group,unit,backend):
    if run(group,unit,backend):
        if backend=='c':run(group,unit,'python')
        raise SystemExit(1)

for group,units in [('identity',['50mm']),('rollback',['50mm','28mm','mount']),('observer_probe',['50mm'])]:
    for unit in units:checked(group,unit,'c')
checked('observer_probe','50mm','python')
for backend in ('c','python'):
    for variant in ('looks18','baseline'):
        os.environ['REVIEW_DAT']=variant
        for unit in ('50mm','mount'):checked('continuation',unit,backend)
print('Auxiliary checks complete',flush=True)
