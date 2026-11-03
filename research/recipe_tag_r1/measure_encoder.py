"""Read an already compiled standalone ELF object; no compiler subprocesses."""
import hashlib
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
c.guard(300)
b=(c.TMP/'tag_encoder.o').read_bytes()
assert b[:6]==b'\x7fELF\x01\x02'
off=struct.unpack_from('>I',b,32)[0]
n,ss=struct.unpack_from('>HH',b,48)
headers=[struct.unpack_from('>10I',b,off+40*k) for k in range(n)]
names=b[headers[ss][4]:headers[ss][4]+headers[ss][5]]
rows=[]
for h in headers:
    name=names[h[0]:].split(b'\0',1)[0].decode()
    if h[2]&2:rows.append(dict(name=name,bytes=h[5],flags=h[2]))
compiler=c.ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
c.dump('encoder_size.json',dict(sections=rows,allocated_bytes=sum(r['bytes'] for r in rows),
       stack_usage=(c.TMP/'tag_encoder.su').read_text(),source_sha256=c.sha(c.HERE/'tag_encoder.c'),
       object_sha256=hashlib.sha256(b).hexdigest(),compiler=str(compiler.relative_to(c.ROOT)),
       compiler_sha256=c.sha(compiler),flags=['-m32r','-Os','-ffreestanding','-fno-builtin','-fPIC','-fstack-usage'],
       scope='isolated unlinked formatter object; no DAT, resident, or camera package'))
c.finish('encoder-size')
print(sum(r['bytes'] for r in rows),'allocated bytes')
