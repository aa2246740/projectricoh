"""Enumerate executable H07 recipe calls, separating API address stores."""
from pathlib import Path
import json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save
import codegen as c
e=c.ES[120];typed={name:x for name,x in e.symbols.items() if x['type']==2 and x['size']}
by_address={}
for name,symbol in typed.items():by_address.setdefault(symbol['address'],name)
rows=[];todo=['ig_event'];seen=set();native=[]
bridges=json.loads((OUT/'final-native-bridges.json').read_text())
while todo:
 name=todo.pop()
 if name in seen:continue
 seen.add(name)
 if name not in typed:
  native.append(name);continue
 symbol=typed[name];lo=symbol['address'];hi=lo+symbol['size'];calls=[];indirect=[]
 for atom in c.atoms(120,name)[0]:
  op=atom['asm'].split(' ',1)[0]
  if op=='jl' or op=='jmp' and atom['asm'].split()[1]!='lr':indirect.append(dict(pc=hex(atom['pc']),asm=atom['asm']))
  if op not in ('bl','bra'):continue
  match=re.search(r'(?:bl|bra) ([0-9a-f]+)',atom['asm']);assert match,atom
  target=int(match[1],16)
  if lo<=target<hi:continue
  resolved=by_address.get(target)
  if resolved is None:
   options=[n for n,s in e.symbols.items() if s['address']==target]
   resolved=options[0] if options else hex(target)
  calls.append(dict(pc=hex(atom['pc']),target=resolved,address=hex(target)));todo.append(resolved)
 rows.append(dict(function=name,address=hex(lo),bytes=symbol['size'],calls=calls,indirect=indirect))
for row in rows:assert not row['indirect'],row
for name in seen:assert name not in ('rv_call','rv_rpc8_native','rv_native_preview','rv_native_alloc','rv_native_sd_id','rv_native_read','rv_native_write'),name
save('h07-recipe-callgraph.json',dict(status='PASS_RECIPE_DIRECT_CALLS',artifacts=json.loads((OUT/'identity.json').read_text())['120'],entry='ig_event',functions=sorted(seen),rows=rows,native_leaves=native,native_bridge_records=bridges,
 note='The ingress stores the rv_call address in its API record but never calls that dispatcher here. Native ready reads 0x200d7fd8 only. The fixed resident close continuation is outside this recipe graph and remains blocked in h07-close-boundary.json.'))
print('PASS H07 recipe direct-call graph',len(rows),'typed bodies; native leaves',native,flush=True)
