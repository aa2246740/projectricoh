"""Conservative dispatcher reachability with the frozen file capability invariant."""
from pathlib import Path
import bisect
import collections
import json
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import codegen as c
from common import OUT,save

allrows={}
for gen in (118,119):
    atoms=c.atoms(gen,'rv_call')[0];pcs=[a['pc'] for a in atoms]
    _,branches,_=c.symbolic(gen,'rv_call',atoms);br={r['atom']:r for r in branches}
    forced={};guards=[]
    for i,a in enumerate(atoms):
        m=re.fullmatch(r'ld24 (\w+),10000(?: <.*>)?',a['asm'])
        if not m:continue
        nearby=atoms[max(0,i-2):i+5]
        assert any('@(340,' in x['asm'] for x in nearby),nearby
        branch=next(j for j in range(i+1,min(i+5,len(atoms))) if j in br and br[j]['opcode'] in ('beqz','bnez'))
        forced[branch]=br[branch]['opcode']=='beqz'
        guards.append(dict(pc=hex(atoms[branch]['pc']),forced_taken=forced[branch],
            context=[dict(pc=hex(x['pc']),asm=x['asm']) for x in nearby]))
    assert len(guards)==3,guards
    indirect=set()
    for base,size in c.table_ranges(gen,'rv_call'):
        for off in struct.unpack('>'+str(size//4)+'i',c.ES[gen].bytes(base,size)):
            indirect.add(bisect.bisect_left(pcs,base+off))
    def successors(i):
        row=atoms[i];op=row['asm'].split(' ')[0]
        if i in br:
            b=br[i];inside=b['logical'].startswith('self@')
            target=int(b['logical'].split('@')[1]) if inside else len(atoms)
            if b['opcode']=='bl':
                return [b['return_atom']]+([target] if inside else [])
            if b['opcode']=='bra':return [target]
            if i in forced:return [target] if forced[i] else [i+1]
            return [target,i+1]
        if op=='jmp':return [] if row['asm']=='jmp lr' else list(indirect)
        return [i+1]
    reached=set();todo=[0]
    while todo:
        i=todo.pop()
        if i>=len(atoms) or i in reached:continue
        reached.add(i);todo.extend(successors(i))
    removed=[hex(atoms[i]['pc']) for i in range(len(atoms)) if i not in reached]
    allrows[gen]=dict(guards=guards,unreachable_pcs=removed,forced_edges=[dict(pc=hex(atoms[i]['pc']),taken=b) for i,b in forced.items()],
        total_atoms=len(atoms),reachable_atoms=len(reached),switch_targets=sorted(hex(pcs[i]) for i in indirect),
        proof='Both final init capability constants exclude 0x10000; valid sessions cannot create a write-mode token. CFG keeps every other conditional edge and over-approximates indirect switch destinations.')
save('file-gate-cfg.json',dict(generations=allrows,
    scope='Only file capability dominance. Unknown data-dependent paths remain open; no observed execution is inferred.'))
print('PASS conservative file-gate CFG',[(g,r['total_atoms']-r['reachable_atoms']) for g,r in allrows.items()],'atoms excluded')
