"""Inspect container growth in an already captured native snapshot."""
import sys,zlib,json
from pathlib import Path
from collections import Counter,deque
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,FAST,HERE
enable();sys.path.insert(0,str(FAST));import wire
path=Path(sys.argv[1]);data=wire.decode(zlib.decompress(path.read_bytes()))
counts=Counter();large=[]
def visit(v,path):
    counts[type(v).__name__]+=1
    if isinstance(v,dict):
        if len(v)>1000:large.append((len(v),path))
        for key,item in v.items():visit(item,path+'/'+str(key))
    elif isinstance(v,(list,tuple,deque,set,frozenset)):
        if len(v)>1000:large.append((len(v),path))
        for i,item in enumerate(v):visit(item,path+'/'+str(i))
visit(data,'root')
result=dict(counts=counts,large=sorted(large,reverse=True)[:40])
print(json.dumps(result,indent=2))
(HERE/'runs/snapshot-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
