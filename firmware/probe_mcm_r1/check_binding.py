"""Exercise every build/ABI byte in the actual resident header gate."""
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n


def main():
    h,p,w=n.boot();n.open_menu(h,p);base=n.pe.SCRATCH+0x800;raw=n.DAT.read_bytes();cases=[]
    def header(blob,length):
        h.b.write(base,blob)
        result=n.require(p.call(h.symbols['rv_header'],(base,length,h.symbols['rv_trust'])))
        return result['r0']
    assert header(raw[:256],len(raw))==0
    for offset,size,label,expected in ((48,32,'body',7),(80,32,'resident',8),(212,16,'ABI',8)):
        for i in range(size):
            damaged=bytearray(raw[:256]);damaged[offset+i]^=1;damaged[20:24]=bytes(4)
            struct.pack_into('>I',damaged,20,zlib.crc32(damaged))
            status=header(damaged,len(raw));assert status==expected,(label,i,status)
            cases.append(dict(field=label,index=i,status=status,header_crc_recomputed=True))
    for length in (0,255,len(raw)-1,len(raw)+1,98305):
        assert header(raw[:256],length)!=0,length
    damaged=bytearray(raw[:256]);damaged[20]^=1
    assert header(damaged,len(raw))==5
    assert not p.rpc.overlay and not any(row['cmd']==22 for row in p.rpc.log)
    n.c.save(n.c.RESEARCH/'evidence/native-binding.json',dict(status='PASS',dat_sha256=n.c.sha(n.DAT),
        positive_header_accepted=True,identity_bytes_tested=80,cases=cases,length_cases=5,bad_header_crc_rejected=True,
        file_MUTATIONS=0,authentication=False))
    print('PASS actual resident header: 80 identity bytes, 5 lengths, CRC; no signature authentication')


if __name__=='__main__':main()
