"""Supplement the factored matrix with real CRC and callee machine code."""
from pathlib import Path
import json,random,sys,zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from execute import Runner,gate_seed,gate_pair,DATA,OUT,save

def main():
    a,b=Runner(116),Runner(117);image,trust=gate_seed();raw=(OUT/'container117.dat').read_bytes();results=[]
    for private in (True,False):
        for unit in range(3):
            c=dict(image=image if private else raw,trust=trust,unit=trust[80+48*unit:92+48*unit],private_base=DATA if private else 0,max_steps=4000000)
            aa,bb,delta,fault=gate_pair(a,b,c,0x900000+unit)
            results.append(dict(private=private,unit=unit,old=aa['result'],new=bb['result'],old_steps=aa['stop']['steps'],new_steps=bb['stop']['steps'],delta=delta,faults=fault,abi=aa['abi_ok'] and bb['abi_ok']))
            print('full gate',private,unit,aa['result'],bb['result'],delta,fault,flush=True)
    rng=random.Random(0x717);crc=[]
    for i in range(128):
        n=rng.randrange(257);data=bytes(rng.getrandbits(8) for _ in range(n));rr=[]
        for r in (a,b):
            r.write(DATA,data);r.reset(i);x=r.call('gxr2_crc32',(DATA,n));rr.append(x)
        aa,bb=rr;ok=aa['result']==bb['result']==zlib.crc32(data) and aa['abi_ok'] and bb['abi_ok'] and aa['stop']['reason']==bb['stop']['reason']=='return'
        crc.append(dict(index=i,length=n,ok=ok,old=aa['result'],new=bb['result']))
    save('full-machine-results.json',dict(gate=results,crc=crc,boundaries='No callee hooks. Only the repository backend executes final ELF instructions.'))
    print('full CRC',len(crc),'failures',sum(not c['ok'] for c in crc),flush=True)
if __name__=='__main__':main()
