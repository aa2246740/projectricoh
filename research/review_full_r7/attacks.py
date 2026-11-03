"""Additional independent attacks. No firmware builds and no writes outside HERE."""
import json
import re
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review as c
import checks as q

def native_getter():
    code=(c.LOCAL/'native/native-get-mode.bin').read_bytes()
    rows=json.loads((c.LOCAL/'native-enum-traces.json').read_text())
    table={r['mode']:r['native_row'] for r in rows}
    results=[]
    for value in range(256):
        regs=[0]*16;regs[14]=0xdeadbeef
        mem={0x200c0dac:0x20500000,0x2050036e:value};pc=0x20271fec;condition=False;trace=[];writes=[]
        for step in range(80):
            if pc==0xdeadbeef:break
            at=pc-0x20271fec;a,b=code[at:at+2];word=(a<<8)|b;trace.append(hex(pc))
            if 0xd0<=a<=0xdf and b==0xc0:
                regs[a&15]=struct.unpack_from('>H',code,at+2)[0]<<16;pc+=4
            elif 0x80<=a<=0x8f and b&0xf0==0xe0:
                regs[a&15]=regs[b&15]|struct.unpack_from('>H',code,at+2)[0];pc+=4
            elif a<0x30 and a>=0x20 and b&0xf0==0xc0:
                regs[a&15]=mem[regs[b&15]];pc+=2
            elif 0xa0<=a<=0xaf and b&0xf0 in (0x90,0x00):
                off=struct.unpack_from('>h',code,at+2)[0];addr=regs[b&15]+off
                if b&0xf0==0x90:regs[a&15]=mem[addr]
                else:mem[addr]=regs[a&15]&255;writes.append([hex(addr),mem[addr]])
                pc+=4
            elif 0xb0<=a<=0xbf:
                assert b>>4==0
                delta=struct.unpack_from('>h',code,at+2)[0]
                pc=(pc&~3)+4*delta if regs[a&15]==regs[b&15] else pc+4
            elif a<16 and b&0xf0==0x40:condition=regs[a]<regs[b&15];pc+=2
            elif a in (0x7d,0x7f):
                delta=b if b<128 else b-256
                pc=(pc&~3)+4*delta if a==0x7f or not condition else pc+2
            elif 0x60<=a<=0x6f:regs[a&15]=b if b<128 else b-256;pc+=2
            elif word in (0x7000,0xf000):pc+=2
            elif word==0x1fce:pc=regs[14]
            else:raise AssertionError((hex(pc),hex(word)))
        assert pc==0xdeadbeef and regs[0]==mem[0x2050036e]
        normalized=regs[0];expected=value if value in (1,3,4,5,6,9,10) else 1
        assert normalized==expected
        assert writes==([] if normalized==value else [['0x2050036e',1]])
        row=table[normalized]
        assert row=={1:2,3:4,4:6,5:7,6:5,9:1,10:3}[normalized]
        results.append(dict(input=value,normalized=normalized,row=row,writes=writes,trace=trace))
    c.save(c.LOCAL/'getter-execution.json',results)
    c.write(c.LOCAL/'native_get_mode.h','static const unsigned native_s_modes[256]={'+','.join(str(r['normalized']) for r in results)+'};\n')
    print('PASS official getter bytes, all 256 inputs; invalid S normalizes to 1 and row 02')

def prepare():
    native_getter()
    src=(c.LOCAL/'review_support.c').read_text()
    src='static int r7_side_effect, r7_corrupt_read;\n'+src
    before='return traced(4,files[fds[fd-17].file].path)?injected_code:original_read(fd,p,n);'
    after='''int fail=traced(4,files[fds[fd-17].file].path);int32_t got;
 if(!fail)return original_read(fd,p,n);
 if(!r7_corrupt_read)return injected_code;
 got=original_read(fd,p,n);if(got>0)((unsigned char *)p)[0]^=1;return got;'''
    assert before in src;src=src.replace(before,after)
    before='int32_t result=traced(5,path)?injected_code:original_write(fd,p,n);'
    after='int fail=traced(5,path);int32_t result=(!fail||r7_side_effect)?original_write(fd,p,n):injected_code;if(fail)result=injected_code;'
    assert before in src;src=src.replace(before,after)
    before='return traced(8,p)?injected_code:original_delete(p);'
    after='int fail=traced(8,p);int32_t got=(!fail||r7_side_effect)?original_delete(p):injected_code;return fail?injected_code:got;'
    assert before in src;src=src.replace(before,after)
    before='return fail?injected_code:original_rename(a,b);'
    after='int32_t got=(!fail||r7_side_effect)?original_rename(a,b):injected_code;if(native_observer)native_observer(27,a);return fail?injected_code:got;'
    assert before in src;src=src.replace(before,after)
    before='return fail?injected_code:rc;'
    after='if(native_observer)native_observer(26,files[fds[fd-17].file].path);return fail?injected_code:rc;'
    assert before in src;src=src.replace(before,after)
    c.write(c.LOCAL/'attack_support.c',src)
    objects=json.loads((c.LOCAL/'host/objects.json').read_text())
    for name,path in [('attacks',c.HERE/'host_attacks.c'),('revision',c.BUILDER/'host_revision.c'),('r6-regression',c.BUILDER/'host_r6_cases.c')]:
        obj=c.LOCAL/'host'/(name+'.o')
        c.run(['/usr/bin/clang',*q.FLAGS,'-I',c.BUILDER,'-c',path,'-o',obj],'compile-'+name)
        c.run(['/usr/bin/clang',*q.FLAGS,*objects,obj,'-o',c.LOCAL/'host'/name],'link-'+name)
    r6=q.parse((c.ROOT/'firmware/engine_v33b/local/full-r6/GXRCE.DAT').read_bytes())
    r7=q.parse(c.CARD.read_bytes());assert r6['golden']==r7['golden']
    for key,row in r7['slots'].items():
        for field in ('entry','record','binding','metadata'):assert row[field]==r6['slots'][key][field]
    diff={}
    for generation in ('engine_v33b','engine_fix_r2'):
        old=c.ROOT/'firmware'/generation;changes=[]
        for p in sorted(c.BUILDER.rglob('*')):
            rel=p.relative_to(c.BUILDER)
            if not p.is_file() or 'local' in rel.parts or rel.suffix not in ('.c','.h','.S','.ld'):continue
            other=old/rel
            if not other.is_file() or c.sha(p)!=c.sha(other):
                changes.append(str(rel))
                if other.is_file():c.run(['/usr/bin/diff','-u',other,p],'source-'+generation+'-'+str(rel).replace('/','-'),allow_failure=True)
        diff[generation]=changes
    c.save(c.LOCAL/'independent-source-comparison.json',diff)
    c.save(c.LOCAL/'r6-r7-data.json',dict(slots=48,entry_record_binding_metadata_identical=True,golden_identical=True))
    print('PASS 48 slots identical to r6; extra drivers compiled from frozen product C')

RESULTS=[]
def execute(binary,name,unit,policy,extra=(),generation=105):
    folders={105:c.OLD,106:c.ROOT/'firmware/full_r4/local/full-r4',107:c.R5,108:c.ROOT/'firmware/engine_v33b/local/full-r6'}
    folder=folders[generation]
    golden=c.LOCAL/f'golden-{generation}.bin'
    if not golden.exists():c.write(golden,q.parse((folder/'GXRCE.DAT').read_bytes())['golden'])
    label='attack-'+binary+'-'+name+'-'+str(unit)+'-'+str(policy)+'-g'+str(generation)+'-'+('-'.join(map(str,extra)) or 'default')
    args=[c.LOCAL/'host'/binary,name,unit,folder/'GXRCE.DAT',c.CARD,c.LOCAL/'trust.bin',golden,c.LOCAL/'r7-golden.bin',policy,*extra]
    result=c.run(args,label,allow_failure=True)
    RESULTS.append(dict(binary=binary,name=name,unit=unit,policy=policy,generation=generation,args=list(extra),rc=result.returncode,log='local/logs/'+label+'.log'))
    if result.returncode:print('FAIL',label,result.stdout[-600:],result.stderr[-1800:])
    return result

def sessions():
    for unit in (0,2):
        for policy in (0,1):
            for slot in range(1,9):
                for action in (0,1,2):execute('attacks','reflexive',unit,policy,[slot,action])
                for initial in (0,1):execute('attacks','power',unit,policy,[slot,initial])
            for prior in range(1,9):
                for new in range(1,9):execute('attacks','deferred',unit,policy,[prior,new])
            execute('revision','write-policy',unit,policy)
            for stage in (5,15,6,26,7,27):
                for nested in (1,6,7,8):execute('attacks','reentry',unit,policy,[stage,nested])
            for op in (2,4,6):
                result=execute('attacks','read-fault',unit,policy,[op,0,0,0])
                counts={int(op):int(n) for op,n in re.findall(r'op(\d+)=(\d+)',result.stdout)}
                for ordinal in range(1,counts[op]+1):
                    for code in (-2,-1,0,257):
                        if op in (2,6) and code>=0:continue
                        execute('attacks','read-fault',unit,policy,[op,ordinal,code,0])
                        if op==4 and code==-1:execute('attacks','read-fault',unit,policy,[op,ordinal,code,1])
            for op in (3,4,5,6,7,8):
                for effect in (0,1):
                    if effect and op not in (5,7,8):continue
                    for code in (-2,-1,0,257):
                        if op in (3,6,7,8) and code>=0:continue
                        execute('attacks','save-fault',unit,policy,[op,1,code,effect])
            execute('attacks','crash-snapshots',unit,policy)
    c.save(c.LOCAL/'independent-attacks.json',RESULTS)
    assert not [r for r in RESULTS if r['rc']]
    print('PASS independent attacks',len(RESULTS))

def extra():
    for policy in (0,1):
        for unit in (0,2):
            for name in ('parent-empty','parent-remember03','poison-write-panel','poison-write-same','poison-rename-panel','poison-close-same','survivor-A','survivor-B','survivor-AB','write-frequency'):
                execute('r6-regression',name,unit,policy)
            for mode in (*range(11),11,255):
                for action in (0,1):execute('revision','boundary',unit,policy,[mode,action,0])
        for generation in (105,106,107,108):
            for unit in range(3):
                for name in ('upgrade-memory','older-card-close'):execute('revision',name,unit,policy,generation=generation)
                if generation==108:
                    for name in ('upgrade-empty','upgrade-saved'):execute('builder-v33',name,unit,policy,generation=generation)
    c.save(c.LOCAL/'extra-regressions.json',RESULTS)
    assert not [r for r in RESULTS if r['rc']]
    print('PASS extra regressions',len(RESULTS))

def older_save():
    for unit in (0,2):
        for policy in (0,1):execute('attacks','older-explicit-save',unit,policy,generation=108)
    c.save(c.LOCAL/'old-DAT-explicit-save.json',RESULTS)
    assert not [r for r in RESULTS if r['rc']]
    print('PASS old DAT explicit save characterization',len(RESULTS))

if __name__=='__main__':
    c.guard();c.unchanged();globals()[sys.argv[1]]();print('unchanged',c.unchanged())
