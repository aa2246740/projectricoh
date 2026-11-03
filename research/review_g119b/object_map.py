"""Pair complete typed data objects by declared name, size and referring functions."""
from pathlib import Path
import collections
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import codegen as c
from common import save

def base(name):return re.sub(r'\.\d+$','',re.sub(r'\.lto_priv\.\d+$','',name))

def main():
    objects={}
    for gen in (118,119):
        users=collections.defaultdict(set);items={}
        for name in c.ES[gen].functions:
            for addr in c.data_targets(gen,name,c.atoms(gen,name)[0]).values():
                obj=c.object_info(gen,addr)
                if obj and obj['type']==1 and obj['name'] not in ('n','g'):
                    users[obj['base']].add(c.canon(gen,name));items[obj['base']]=obj
        objects[gen]={addr:dict(obj=obj,users=sorted(users[addr])) for addr,obj in items.items()}
    pairs=[];unmatched=[]
    for addr,x in objects[118].items():
        matches=[y for y in objects[119].values() if base(x['obj']['name'])==base(y['obj']['name'])
            and x['obj']['size']==y['obj']['size'] and x['users']==y['users']]
        if len(matches)!=1:
            unmatched.append(dict(old=x,candidates=matches));continue
        y=matches[0];a,b=x['obj'],y['obj']
        _,aa=c.object_bytes(118,a,a['base']);_,bb=c.object_bytes(119,b,b['base'])
        if a['name']=='rv_api':
            aa,bb=bytearray(aa),bytearray(bb)
            assert int.from_bytes(aa[16:20],'big')==c.ES[118].functions['rv_call']['address']
            assert int.from_bytes(bb[16:20],'big')==c.ES[119].functions['rv_call']['address']
            aa[16:20]=bb[16:20]=bytes(4)
        assert aa==bb,(a,b)
        pairs.append(dict(old=a,new=b,users=x['users'],bytes_equal=True))
    assert len({p['new']['base'] for p in pairs})==len(pairs)
    save('object-map.json',dict(pairs=pairs,unmatched=unmatched))
    print('OBJECT PAIRS',len(pairs),'unmatched',[(x['old']['obj']['name'],x['old']['users']) for x in unmatched],flush=True)

if __name__=='__main__':main()
