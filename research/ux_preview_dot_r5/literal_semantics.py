"""Check the new RAM helpers against literal, complete expected memory images."""
from pathlib import Path
import hashlib,json,random,struct,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import differential as d
from common import OUT,save,sha

def run(name,count=10000):
    r=d.ex.Runner(120);g=d.BASE+r.e.symbols['g']['address'];n=r.n
    recipe_out=d.DATA+0x27000
    rng=random.Random(0x120c5);rows=[];edges=set();started=time.monotonic();digest=hashlib.sha256();owned=[0];calls=[]
    if name=='start_view':
        def boundary(b):calls.append(tuple(b.core.r[:3]));return owned[0]
        r.hook('view_owned',boundary)
    elif name=='view_owned':
        def boundary(b):calls.append(tuple(b.core.r[:3]));return owned[0]
        r.hook('rv_view_owned',boundary)
    else:assert name=='accept_preview'
    for index in range(count+64):
        gb=bytearray(rng.randbytes(r.e.symbols['g']['size']));nb=bytearray(rng.randbytes(r.e.symbols['n']['size']))
        unit=rng.randrange(3);slot=rng.randrange(1,9)
        directory=int.from_bytes(d.IMAGE[156:160],'big')+64*unit;bank=int.from_bytes(d.IMAGE[directory+16:directory+20],'big')
        record=d.IMAGE[bank+32+64*(slot-1):bank+96+64*(slot-1)]
        ref=bytes([unit,slot])+record[2:3]+record[4:36]+record[3:4]+record[36:51]
        gb[184:235]=ref;gb[286:294]=rng.randbytes(8)
        ready=(index>>1)&1;busy=(index>>2)&1;uncertain=index&1;panel=(index>>3)&1;watch=(index//16)%3
        gb[2523]=ready;gb[2525]=busy;gb[2527]=uncertain;nb[550]=panel;nb[3713]=watch
        struct.pack_into('>I',nb,4,d.CTX)
        r.write(g,gb);r.write(n,nb);r.write(d.CTX+8,struct.pack('>I',d.ROOT_ADDR))
        eg,en=bytearray(gb),bytearray(nb);calls.clear();owned[0]=index&1
        if name=='accept_preview':
            expected=2 if uncertain else 3 if not ready or busy else 0
            if expected==0:
                eg[235:286]=gb[184:235];eg[294:302]=gb[286:294];eg[2535]=1;eg[2536]=0;eg[2533]=5
                at=1356+(slot-1)*8;en[at:at+8]=gb[286:294]
        elif name=='start_view':
            expected=owned[0];en[3713]=2 if panel else 1;en[3714]=en[3715]=0;eg[2537]=0
        else:
            expected=owned[0]
        r.reset(0x120c5000+index);result=r.call(name,(),steps=100000)
        actual_g=r.read(g,len(gb));actual_n=r.read(n,len(nb));edges.update(map(tuple,result['edges']))
        unexpected=[]
        for address,data,pc in result['writes']:
            if not (d.STACK<=address<d.STACK+0x10000 or g<=address<g+len(gb) or n<=address<n+len(nb)):
                unexpected.append(dict(address=hex(address),bytes=data,pc=hex(pc)))
        args_ok=True
        if name=='view_owned':
            layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
            expected_list=n+layout['panel.list'] if panel or watch==2 else n+layout['list']
            # Offsets come from the actual Integrated/PnPanel wire layout.
            args_ok=len(calls)==1 and calls[0][0]==d.ROOT_ADDR and calls[0][1]==expected_list and calls[0][2]==0
        ok=result['stop']['reason']=='return' and result['result']==expected and result['abi_ok'] and actual_g==eg and actual_n==en and not unexpected and args_ok
        row=dict(index=index,kind='random' if index<count else 'boundary',ready=ready,busy=busy,uncertain=uncertain,panel=panel,watch=watch,expected=expected,actual=result['result'],ok=ok)
        rows.append(row)
        if not ok:
            save('literal/'+name+'-failure.json',dict(row=row,result=result,expected_g=eg.hex(),actual_g=actual_g.hex(),expected_n=en.hex(),actual_n=actual_n.hex(),unexpected=unexpected,calls=calls));raise AssertionError((name,index))
        digest.update(actual_g);digest.update(actual_n)
        if index%2000==0:print('C literal',name,index,'/',count,flush=True)
    folder=OUT/'literal';folder.mkdir(exist_ok=True)
    (folder/(name+'-cases.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    save('literal/'+name+'-results.json',dict(status='PASS',function=name,random=count,boundary=64,edges=sorted(edges),memory_sha256=digest.hexdigest(),
        dat=sha(r.original),elf=sha(r.e.raw),comparison='Literal complete g/n memory images, return value, preserved ABI, no other public memory writes.',seconds=time.monotonic()-started))
    print('PASS C literal',name,count,'+64',flush=True)

if __name__=='__main__':run(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 10000)
