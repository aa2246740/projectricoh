"""Extract immutable body/unit maps for the slot31 request, not guessed replies."""
from pathlib import Path
import json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.compute_gate('slot31-static-r2');out=C.LOCAL/'accept-r2/slot31';out.mkdir(parents=True,exist_ok=True)
sources={}
for name,path in [('body',C.ROOT/'firmware/image_v310/local/ilaunch3'),('mount',C.ROOT/'artifacts/firmware/gxr-1.51/l08firm3')]:
    raw=path.read_bytes();sections=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)];rows=[]
    for i,(offset,base,n,a,b) in enumerate(sections):
        if not n or not 0x20000000<=base<0x20800000 or 512+offset+n>len(raw):continue
        target=out/(name+'-'+str(i)+'.bin');target.write_bytes(raw[512+offset:512+offset+n])
        result=C.run([C.OBJDUMP,'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+hex(base),target],'r2-slot31-'+name+'-'+str(i))
        text=out/(name+'-'+str(i)+'.txt');text.write_text(result.stdout)
        rows.append(dict(index=i,offset=offset,base=base,length=n,flags=[a,b],disassembly=str(text.relative_to(C.ROOT))))
    sources[name]=dict(path=str(path.relative_to(C.ROOT)),sha256=C.sha(raw),sections=rows)
C.save(out/'sources.json',dict(status='EXTRACTED',sources=sources,scope='Static firmware bytes and disassembly only; no claim of a device response.'))
print(json.dumps(dict(status='EXTRACTED',sources={k:len(v['sections']) for k,v in sources.items()})))
