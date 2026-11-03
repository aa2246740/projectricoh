#!/usr/bin/env python3
"""Reproduce focused native contexts and final engine-byte bindings."""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review', HERE / 'review.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

GROUPS = {
 'hook-focus.txt': [('h01',0x20287030,0x202871c0),('h05',0x201feb50,0x201fec54),
                    ('h06',0x202be204,0x202be2a0),('h07',0x202871c0,0x202872d0),
                    ('h08',0x202bb908,0x202bb9c0),('h09',0x20170938,0x20170a20),
                    ('update',0x2036d4e8,0x2036d620)],
 'native-ui-indexing.txt': [('fn2 epilogue',0x202be694,0x202be6c4),
                          ('commit epilogue',0x202bcf40,0x202bcf90),
                          ('ADJ caller',0x202ba6e0,0x202ba7b4),
                          ('details indexing',0x201fecb0,0x201fee28)],
 'heap-native.txt': [('native allocator and free',0x2005bee0,0x2005c108)],
 'h07-and-row-context.txt': [('H07 close A',0x202b8d50,0x202b8dcc),
                            ('H07 close B',0x202bd830,0x202bd8b0),
                            ('H07 close C',0x202bea20,0x202bea90),
                            ('H07 keep/close D',0x202c2d40,0x202c2da0),
                            ('native cursor',0x202c25b8,0x202c26d0),
                            ('renderer cursor',0x201fe440,0x201fe498)],
 'h07-caller-returns.txt': [('A',0x202b9040,0x202b90c0),('B',0x202bdc00,0x202bdc54),
                          ('C',0x202bec38,0x202bec90),('D',0x202c31b0,0x202c3280)],
 'update-confirmation-context.txt': [('entry',0x2036d560,0x2036d578),
                                    ('helper UI call',0x2036d340,0x2036d370),
                                    ('native UI helper',0x202e4f44,0x202e5034)]
}


def main():
    r.preflight()
    logs=[]
    def dump(rel, dest):
        cmd=[str(r.OBJDUMP),'-d',str(r.LOCAL/'frozen'/rel)]
        p=subprocess.run(cmd,capture_output=True,text=True)
        logs.append(dict(argv=cmd,returncode=p.returncode,output='local/disasm/'+dest,stderr=p.stderr))
        assert p.returncode==0,p.stderr
        (r.LOCAL/'disasm'/dest).write_text(p.stdout)
    dump('firmware/resident_v3/local/resident/engine-services/services-linkcheck.elf','services.txt')
    dump('firmware/resident_v3/local/product/m32r-lto/engine.elf','product.txt')
    bindings=[]
    for name in ('life','notice','view'):
        rel='firmware/resident_v3/local/probes/build/'+name+'/engine.elf'
        dump(rel,'probe-'+name+'.txt')
        raw=(r.LOCAL/'frozen'/rel).read_bytes();secs,_=r.elf_parse(raw);s=secs['.engine']
        container=(r.LOCAL/('frozen/firmware/resident_v3/local/probes/candidates/'+name+'/GXRCE.DAT')).read_bytes()
        off,n=struct.unpack_from('>II',container,132)
        assert raw[s['offset']:s['offset']+s['size']]==container[off:off+n]
        bindings.append(dict(name=name,whole_code_matches_elf=True))
    raw=(r.LOCAL/'frozen/firmware/resident_v3/local/product/m32r-lto/engine.elf').read_bytes()
    secs,_=r.elf_parse(raw);s=secs['.engine'];code=raw[s['offset']:s['offset']+s['size']]
    huzi=(r.LOCAL/'frozen/firmware/resident_v3/local/product/candidates/huzi/GXRCE.DAT').read_bytes()
    base=(r.LOCAL/'frozen/firmware/resident_v3/local/product/candidates/base/GXRCE.DAT').read_bytes()
    off,n=struct.unpack_from('>II',huzi,132);boff,bn=struct.unpack_from('>II',base,132)
    assert code==huzi[off:off+n]
    assert huzi[off+0x7940-256:off+0x794c-256]==base[boff+0x7940-256:boff+0x794c-256]
    bindings += [dict(name='huzi',whole_code_matches_elf=True),
                 dict(name='base',row_instructions_match_huzi=True,whole_code_identical_to_huzi=False)]
    r.save('engine-byte-bindings.json',bindings)
    r.save('additional-commands.json',logs)
    selected={key:[] for key in GROUPS}
    for path in sorted((r.LOCAL/'disasm').glob('official-*.txt')):
        for line in path.read_text().splitlines():
            m=re.match(r'^([0-9a-f]+):',line)
            if not m:continue
            pc=int(m[1],16)
            for key,windows in GROUPS.items():
                if any(start<=pc<end for _,start,end in windows):selected[key].append((pc,line))
    for key,windows in GROUPS.items():
        text=[]
        for label,start,end in windows:
            text.append('\n'+label)
            text += [line for pc,line in selected[key] if start<=pc<end]
        (r.LOCAL/key).write_text('\n'.join(text)+'\n')
    calls=[]
    for name in ('resident','services'):
        function=None
        for line in (r.LOCAL/('disasm/'+name+'.txt')).read_text().splitlines():
            m=re.match(r'^[0-9a-f]+ <([^>]+)>:',line)
            if m:function=m[1]
            if re.search(r'\bbl .*<rv_irq_(save|restore)>',line):
                calls.append(dict(file=name+'.txt',function=function,instruction=line))
    assert len(calls)==29
    r.save('irq-call-sites.json',calls)
    orig=(r.LOCAL/'frozen'/r.OFFICIAL).read_bytes()
    segments=json.loads((r.LOCAL/'segments.json').read_text())
    def at(va,n):
        s=next(s for s in segments if s['va']<=va and va+n<=s['va']+s['size'])
        off=s['offset']+va-s['va'];return orig[off:off+n]
    table=[]
    for i in range(22):
        delta=struct.unpack('>h',at(0x20377434+2*i,2))[0]
        table.append(dict(activity=i+1,entry_address=0x20377434+2*i,target=(0x202ba72c+delta)&~3))
    assert [x['activity'] for x in table if x['target']==0x202ba764]==[8]
    r.save('h01-native-activity-table.json',table)
    r.save('native-heap-data.json',dict(heap_base=int.from_bytes(at(0x200c0dc0,4),'big'),
           heap_bytes=int.from_bytes(at(0x200c0dc4,4),'big'),allocated_length_includes_header_bytes=12))
    print('NATIVE_CONTEXTS_PASS engine_bindings=5 irq_calls=29 H01_activity=8')


if __name__=='__main__':
    main()
