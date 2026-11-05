"""Append independent cold paths to the single load-aware queue."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
rows=json.loads((C.LOCAL/'persistence/sources.queue.json').read_text())
for profile in ('test','release'):
    for unit in C.UNITS:
        label=f'final-native-{profile}-{unit}-sweep'
        args=['--version',profile,'--unit',unit,'--backend','native','--label',label,'--action','sweep']
        rows.append(dict(label=label,args=args,log=str(C.LOCAL/'logs'/(label+'.log'))))
C.save(C.LOCAL/'cold.queue.json',rows)
