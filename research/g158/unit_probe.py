"""Preserve a narrow unit RPC registration disassembly for the missing boundary."""
from pathlib import Path
import json,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.compute_gate('unit-RPC31-investigation')
out=C.LOCAL/'unit-probe-r2';out.mkdir(exist_ok=True)
raw=(C.ROOT/'artifacts/firmware/gxr-1.51/l08firm3').read_bytes();sections=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)]
address=0x201a7000;length=0x2000
offset,base,n,_,_=next(r for r in sections if r[1]<=address and address+length<=r[1]+r[2])
code=raw[512+offset+address-base:512+offset+address-base+length];file=out/'registration.bin';file.write_bytes(code)
r=C.run([C.OBJDUMP,'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+hex(address),file],'unit-rpc-registration-r2')
(out/'registration.txt').write_text(r.stdout)
C.save(out/'source.json',dict(unit_sha256=C.sha(raw),address=address,length=length,scope='Read-only local unit disassembly. No successful peer response is assumed.'))
print(json.dumps(dict(status='EXTRACTED',path=str(out/'registration.txt'))))
