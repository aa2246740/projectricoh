"""Bounded native instruction excerpts, pinned to the fixed g153 image."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s

def read(address,size):
    import struct
    raw=s.BODY.read_bytes()
    for i in range(16):
        source,base,n,_,_=struct.unpack_from('>5I',raw,0x20+20*i)
        if base<=address and address+size<=base+n:return raw[source+0x200+address-base:source+0x200+address-base+size]
    raise ValueError(hex(address))

def main():
    s.enable()
    for name,start,end in (('parse',0x20166944,0x20166dbc),('slots',0x2016c060,0x2016c65c),
       ('source-word',0x20166660,0x20166944),('producer',0x201705f0,0x201709a0),('size-rule',0x2016be84,0x2016c060),
       ('osd-init',0x201bdec8,0x201be074),('size-core',0x2016bde0,0x2016be84),
       ('palette-fill',0x201be698,0x201be940),
       ('palette-driver',0x200e1610,0x200e1750),('mode-map',0x20169c28,0x20169ce4),('dimensions',0x2016b95c,0x2016bde0),
       ('palette-register',0x203d04c8,0x203d05c8),
       ('palette-get',0x203d0390,0x203d04c8),
       ('palette-convert-end',0x203d05c8,0x203d0628),
       ('allocate',0x2016a040,0x2016a168),('dispatch',0x20173a10,0x20173b40),('palette',0x201be074,0x201be214)):
        path=s.TMP/(name+'.bin');path.write_bytes(read(start,end-start))
        result=s.run([s.OBJDUMP,'-D','-b','binary','-m','m32r','-EB','--adjust-vma='+hex(start),path],'native-'+name)
        (s.HERE/'evidence'/('native-'+name+'.txt')).write_text(result.stdout)

if __name__=='__main__':main()
