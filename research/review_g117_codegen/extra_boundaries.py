"""Small explicit off-by-one and NULL matrices supplement the random inputs."""
from pathlib import Path
import json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from primary import compared
from execute import Runner,DATA,BASE,OUT,save
def main():
    a,b=Runner(116),Runner(117);p=DATA+0x1000;s=DATA+0x2000;n=DATA+0x3000;gg=DATA+0x4000;rows=[]
    cases=[('cursor-'+str(c),None,None,c) for c in (0,1,9,10,11,12,255)]
    cases += [('NULL-arg-'+str(i),'arg',i,5) for i in range(4)]
    cases += [('NULL-seed-'+str(i),'seed',i,5) for i in range(3)]
    cases += [('size-%d-%d'%(i,v),'size',(i,v),5) for i,z in enumerate((32,72,132)) for v in (0,1,z-1,z,z+1,0xffffffff)]
    cases += [('state-'+str(v),'state',v,5) for v in (0,1,4,5,6,255)]
    cases += [('glyph-zero-'+str(i),'glyph',i,5) for i in range(11)]
    edges={116:set(),117:set()}
    for i,(name,kind,v,cursor) in enumerate(cases):
        args=[s,p,n,gg]
        for r in (a,b):
            r.write(p,bytes(48));r.w32(p+40,BASE+r.e.functions['address']['address'])
            r.write(s,struct.pack('>6I',DATA+0x5000,DATA+0x6000,DATA+0x7000,32,72,132));r.write(DATA+0x5000,bytes([5])+bytes(31));r.write(DATA+0x6000,bytes(72));r.write(DATA+0x7000,bytes(132));r.write(n,bytes(324));r.write(gg,struct.pack('>11I',*(DATA+0x10000+16*j for j in range(11))))
            if kind=='seed':r.w32(s+4*v,0)
            if kind=='size':r.w32(s+12+4*v[0],v[1])
            if kind=='state':r.write(DATA+0x5000,bytes([v]))
            if kind=='glyph':r.w32(gg+4*v,0)
        if kind=='arg':args[v]=0
        aa,bb,raw_equal=compared(a,b,'pn_native_from_seed',args,i,(cursor,))
        ext=lambda x:[(ad,d) for ad,d,pc in x['writes'] if DATA<=ad<DATA+0x30000]
        ok=aa['result']==bb['result'] and aa['saved']==bb['saved'] and aa['abi_ok'] and bb['abi_ok'] and aa['stop']['reason']==bb['stop']['reason']=='return' and ext(aa)==ext(bb)
        rows.append(dict(name=name,old=aa['result'],new=bb['result'],equal=ok))
        for g,x in ((116,aa),(117,bb)):edges[g].update(x['edges'])
    save('native-boundaries.json',dict(cases=rows,edges={g:[(hex(pc),t) for pc,t in sorted(e)] for g,e in edges.items()}));print('native boundaries',len(rows),'failures',sum(not r['equal'] for r in rows))
if __name__=='__main__':main()
