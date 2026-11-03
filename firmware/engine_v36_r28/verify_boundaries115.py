"""Exercise the frozen resident validator on the final real envelope."""
import json
from pathlib import Path
import struct
import sys
import zlib

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'candidate'))
import common as c


def main():
    c.guard();out=HERE/'local/envelope115';out.mkdir(exist_ok=True)
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST',
        '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',c.RESIDENT]
    objects=[]
    for i,source in enumerate((HERE/'envelope115.c',c.RESIDENT/'validate_envelope.inc.c',
            c.RESIDENT/'runtime.c',c.UPSTREAM/'local/resident/trust.c')):
        obj=out/f'{i}.o';objects.append(obj)
        extra=['-Dmemcpy=rv_memcpy','-Dmemset=rv_memset'] if source.name=='runtime.c' else []
        c.run(['/usr/bin/clang',*flags,*extra,'-c',source,'-o',obj],f'envelope-compile-{i}')
    binary=out/'validate';c.run(['/usr/bin/clang',*flags,*objects,'-o',binary],'envelope-link')
    original=(c.LOCAL/'full-r13/GXRCE.DAT').read_bytes()
    def seal(raw):
        struct.pack_into('>I',raw,24,zlib.crc32(raw[256:]));struct.pack_into('>I',raw,20,0)
        struct.pack_into('>I',raw,20,zlib.crc32(raw[:256]));return raw
    word=lambda off:struct.unpack_from('>I',original,off)[0]
    cases=[('valid',bytearray(original),0)]
    for label,off,value,expected in [('zero-generation',28,0,3),('entry-outside',112,0,6),
            ('image-overflow',116,114688-len(original)+4,2),
            ('overlap',156,word(132),6),('reloc-patch',word(144),257,15),
            ('reloc-target',word(144)+4,0,15)]:
        raw=bytearray(original);struct.pack_into('>I',raw,off,value);cases.append((label,seal(raw),expected))
    for label,off,expected in [('wrong-body',48,7),('wrong-build',80,8),('wrong-abi',212,8)]:
        raw=bytearray(original);raw[off]^=1;cases.append((label,seal(raw),expected))
    raw=bytearray(original);struct.pack_into('>H',raw,120,257);cases.append(('reloc-count',seal(raw),15))
    for label,off in [('header-crc',20),('payload-crc',256)]:
        raw=bytearray(original);raw[off]^=1;cases.append((label,raw,5))
    raw=bytearray(original)+bytearray(98308-len(original));struct.pack_into('>I',raw,16,len(raw))
    cases.append(('over-98304',seal(raw),2))
    results=[]
    for label,raw,expected in cases:
        path=out/(label+'.DAT');path.write_bytes(raw)
        result=c.run([binary,path],'envelope-'+label);actual=int(result.stdout)
        assert actual==expected,(label,expected,actual)
        results.append(dict(case=label,expected=expected,actual=actual))
    (out/'results.json').write_text(json.dumps(dict(status='PASS',cases=results),indent=2)+'\n')
    print('PASS frozen resident envelope validator:',len(results),'real-artifact cases')


if __name__=='__main__':main()
