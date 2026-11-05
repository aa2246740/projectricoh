from pathlib import Path
import struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.compute_gate('unit-RPC31-handler');out=C.LOCAL/'unit-handler31';out.mkdir(exist_ok=True)
raw=(C.ROOT/'artifacts/firmware/gxr-1.51/l08firm3').read_bytes();sections=[struct.unpack_from('>5I',raw,32+20*i) for i in range(16)]
a=0x201f7800;n=0x1000;offset,base,length,_,_=next(r for r in sections if r[1]<=a and a+n<=r[1]+r[2]);p=out/'handler.bin';p.write_bytes(raw[512+offset+a-base:512+offset+a-base+n])
r=C.run([C.OBJDUMP,'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+hex(a),p],'unit-rpc31-handler');(out/'handler.txt').write_text(r.stdout)
print('EXTRACTED MOUNT RPC31 handler at 0x201f78ac; no result assumed')
