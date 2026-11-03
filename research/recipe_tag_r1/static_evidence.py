"""Bind selected disassembly windows to original and existing body bytes.

Only reads already available disassembly; does not build firmware or change an
analysis database. Address ranges and code identities are reproducible inputs.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
c.guard(600)


class Image:
    def __init__(self,path):
        self.path=path;self.raw=path.read_bytes()
        self.sections=[struct.unpack_from('>5I',self.raw,0x20+20*i) for i in range(16)]
    def offset(self,address,n):
        for src,base,size,_,_ in self.sections:
            if base<=address and address+n<=base+size:return src+0x200+address-base
        raise ValueError('Unmapped file range')
    def read(self,address,n):
        off=self.offset(address,n);return self.raw[off:off+n]


WINDOWS={
    'dng-constructor':(0x20121c38,0x20121c80),
    'dng-usercomment':(0x20124cec,0x20124d7c),
    'jpeg-usercomment':(0x20128694,0x201286e0),
    'comment-helper-dng':(0x20126dcc,0x20126e10),
    'comment-helper-jpeg':(0x201273c4,0x20127408),
    'dng-copyright':(0x20122840,0x201228d4),
    'jpeg-copyright':(0x20127ea8,0x20127f78),
    'jpeg-header-after-encoder':(0x2015f674,0x2015f6e0),
    'raw-metadata-and-header':(0x201676f0,0x20167880),
    'append-seek-wrapper':(0x200a4f40,0x200a5074),
    'buffered-close':(0x200a437c,0x200a449c),
    'filename-counter-candidates':(0x201166e8,0x20116838),
    'exif-capture-time-source':(0x20128218,0x201282b0),
}


def main():
    stock=Image(c.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3')
    body=Image(c.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/ilaunch3')
    listings={}
    for section in (1,4,6):
        p=c.ROOT/f'research/xpan_incamera/local/disasm/ilaunch3-{section:02d}.txt'
        for line in p.read_text().splitlines():
            m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',line)
            if m:listings[int(m[1],16)]=(bytes.fromhex(m[2]),m[3])
    rows=[]
    for name,(lo,hi) in WINDOWS.items():
        data=stock.read(lo,hi-lo);lines=[]
        for at,(raw,asm) in listings.items():
            if lo<=at<hi:
                assert stock.read(at,len(raw))==raw
                lines.append(f'{at:08x}: {raw.hex()} {asm}')
        rows.append(dict(name=name,start=hex(lo),end=hex(hi),file_offset=hex(stock.offset(lo,hi-lo)),
                         sha256=hashlib.sha256(data).hexdigest(),v39_equal=body.read(lo,hi-lo)==data,
                         instruction_count=len(lines)))
        (c.HERE/'local').mkdir(exist_ok=True)
        (c.HERE/'local'/(name+'.asm.txt')).write_text('\n'.join(lines)+'\n')
    tags={}
    for name in ('ilaunch3','jlaunch3','qlaunch3','l08firm3'):
        im=Image(c.ROOT/'artifacts/firmware/gxr-1.51'/name)
        p=c.ROOT/'research/xpan_incamera/local/disasm'/(name+'-04.txt')
        found=[]
        for line in p.read_text().splitlines():
            m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',line)
            if m and ('ld24 r4,0x9286' in m[3] or 'ld24 r4,0x8298' in m[3] or 'ldi r4,#270' in m[3]):
                at=int(m[1],16);raw=bytes.fromhex(m[2]);assert im.read(at,len(raw))==raw
                found.append(dict(vma=hex(at),file_offset=hex(im.offset(at,len(raw))),instruction=m[3]))
        tags[name]=dict(sha256=hashlib.sha256(im.raw).hexdigest(),bounded_search='existing section-04 disassembly only',tag_writers=found)
    c.dump('static_evidence.json',dict(official_sha256=hashlib.sha256(stock.raw).hexdigest(),
           v39_sha256=hashlib.sha256(body.raw).hexdigest(),windows=rows,tag_writers=tags,
           template_bytes={hex(at):dict(sha256=hashlib.sha256(stock.read(at,264)).hexdigest(),
                          v39_equal=body.read(at,264)==stock.read(at,264),
                          prefix=repr(stock.read(at,40))) for at in (0x201419e9,0x20141afd)}))
    c.finish('static')
    print('PASS',len(rows),'byte-bound windows')


if __name__=='__main__':main()
