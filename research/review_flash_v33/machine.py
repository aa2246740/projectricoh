"""Execute final resident instructions and a bounded native constructor model."""
import itertools
import json
import re
import shutil
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import review as c
import artifacts as a
from host import module

RES=c.ROOT/'firmware/resident_v33'
OUT=c.LOCAL/'machine'

def load_policy():
    p=module(RES/'policy_machine.py','policy_model')
    OUT.mkdir(parents=True,exist_ok=True);p.LOCAL=OUT
    return p

def ownership():
    p=load_policy();program=p.Program('resident',RES/'local/resident/build/resident.elf')
    old=p.Program('v32',c.ROOT/'firmware/resident_v32/local/resident/build/resident.elf')
    entry=module(RES/'entry_machine.py','entry_fixture');entry.p=p
    rows=[]
    for hook,count,tag,row,state in itertools.product((1,2,5),(1,2),(0,31,32,33,34),range(1,9),(0x2022f71c,0x2022d610,0x2072aaaa)):
        cpu=entry.observe(program,hook,count,tag,row,state)
        expected=(tag==33 and state==0x2022f71c) or (hook<=2 and count==1 and tag==32)
        assert cpu.read(p.FRAME+4)==(program.symbols[f'rv_skip_{hook:02}'] if expected else 0)
        if expected and hook<=2:assert cpu.read(p.FRAME+(60 if hook==1 else 28))==row
        rows.append(dict(hook=hook,count=count,tag=tag,row=row,state=hex(state),takeover=expected))
    # Negate each surviving ownership requirement independently at the machine boundary.
    mutations=[('root_magic',p.ROOT_ADDRESS,0,4),('root_version',p.ROOT_ADDRESS+4,31,1),
        ('root_state',p.ROOT_ADDRESS+5,6,1),('not_published',p.ROOT_ADDRESS+156,0,4),
        ('labels_changed',0x2022f5a8,0x2022d610,4),('other_item',0x205d9bf8,7,4),
        ('other_value',0x205d9c00,55,4),('other_part',0x205a280f,1,1),
        ('other_array',0x205a27d8,0x2072aaaa,4),('empty_stack',0x205a27d4,0,1),('too_deep',0x205a27d4,3,1)]
    rejected=[]
    # Capture the seed prepared by observe(), then execute again with one changed field.
    for hook,(name,address,value,n) in itertools.product((2,5),mutations):
        seed=entry.observe(program,hook,1,32 if hook==2 else 33,8,0x2022f71c)
        seed.seed(p.FRAME+4,0);seed.seed(address,value,n)
        # rv_retire on malformed root is a named boundary in this policy check.
        seed.stubs[program.symbols['rv_retire']]=lambda cpu:cpu.r.__setitem__(0,0)
        seed.run('rv_hook_observe',[p.ROOT_ADDRESS,hook,p.FRAME])
        assert seed.read(p.FRAME+4)==0,(hook,name)
        rejected.append(dict(hook=hook,requirement=name))
    for hook,row in itertools.product((1,2),range(1,9)):
        cpu=entry.observe(old,hook,1,32,row,0x2022d610);assert not cpu.read(p.FRAME+4)
    c.write('machine-ownership.json',dict(status='PASS',cases=len(rows),cases_detail=rows,
        boundary_rejections=rejected,v32_negative_controls=16,objdump_bytes_verified=program.verified_bytes,native_execution=False))
    print('PASS compiled owned() cases',len(rows),'boundaries',len(rejected),'v32 negatives',16,flush=True)

def constructor():
    p=load_policy();program=p.Program('resident-constructor',RES/'local/resident/build/resident.elf')
    # Combine actual packaged constructor/hook bytes with the final ELF, without a synthetic firmware build.
    body=(a.PACKAGE/'SD_ROOT/ilaunch3').read_bytes()
    lo,hi=0x20287080,0x202871d8;raw=a.image_at(body,lo,hi-lo)
    text,_=a.disasm('constructor-final',raw,lo)
    program.spans.append((lo,raw));program.symbols['constructor']=lo
    for line in text.splitlines():
        m=re.match(r'^\s*([0-9a-f]+):\t([0-9a-f ]+)\t(.*)',line)
        if not m:continue
        pc=int(m[1],16);b=bytes.fromhex(m[2]);assert b==bytes(program.byte(pc+i) for i in range(len(b)))
        program.width[pc]=len(b);program.code[pc]=tuple(program.parse(x) for x in re.split(r' -> | \|\| ',m[3]))
    calls=[];cases=0
    cursor=json.loads((RES/'local/resident/target-layout.json').read_text())['RvSession']['fields']['cursor']['offset']
    for row,mode in itertools.product(range(1,9),range(256)):
        cpu=p.fresh(program)
        for address,value,n in [(p.ROOT_ADDRESS+156,0x2022d610,4),(p.ROOT_ADDRESS+180,0x20724100,4),
                (0x2022f5a8,0x20724100,4),(0x205d9bf8,8,4),(0x205d9c00,56,4),(0x205a280f,2,1),
                (p.NATIVE,32,1),(p.NATIVE+4,0x2022d610,4),(p.SESSION+cursor,row-1,4),(0x2050036e,mode,1)]:cpu.seed(address,value,n)
        cpu.stubs={program.symbols['rv_check']:lambda x:x.r.__setitem__(0,0),
                   program.symbols['rv_session']:lambda x:x.r.__setitem__(0,p.SESSION),
                   program.symbols['rv_engine']:lambda x:x.r.__setitem__(0,1)}
        # Native calls preserve callee-saved r8 and are outside this bounded constructor execution.
        def push(x):
            assert x.r[4:8]==[2,33,0x2022f71c,0]
            assert x.read(0x2022f725,1)==row==x.read(0x2022f726,1)
            x.write(p.NATIVE+8,33,1);x.write(p.NATIVE+12,0x2022f71c);x.write(0x205a27d4,2,1);x.r[0]=1
        for target in (0x20331d18,0x2028579c,0x20285724,0x201c06f4,0x201c092c,0x20331d14):
            cpu.stubs[target]=lambda x:x.r.__setitem__(0,0)
        cpu.stubs[0x201c07e0]=push
        cpu.run('constructor',bound=3000)
        assert 0x20271fec not in cpu.calls
        assert cpu.read(0x2022f725,1)==row==cpu.read(0x2022f726,1)
        assert cpu.read(0x2050036e,1)==mode
        assert cpu.read(0x205a27d4,1)==2
        cases+=1
    c.write('constructor-machine.json',dict(status='PASS',vectors=cases,rows=8,S_values=256,
        actual_packaged_constructor_and_resident=True,getter_not_called=True,stores_before_tag33=True,
        native_calls_doubled=True,native_execution=False))
    print('PASS packaged native constructor + final resident',cases,flush=True)

def replay():
    m=module(RES/'machine_checks.py','resident_replay')
    m.LOCAL=OUT/'replay';(m.LOCAL/'resident/build').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(RES/'local/resident/build/resident.elf',m.LOCAL/'resident/build/resident.elf')
    shutil.copyfile(RES/'local/resident/hooks.json',m.LOCAL/'resident/hooks.json')
    m.replay();m.h07_paths()

def irq():
    m=module(RES/'machine_checks.py','irq_model')
    elf=a.Elf(RES/'local/resident/build/resident.elf')
    save=elf.at(elf.symbols['rv_irq_save']['va'],12);restore=elf.at(elf.symbols['rv_irq_restore']['va'],4)
    paths=[RES/'local/resident/build/resident.elf',RES/'local/resident/engine-services/services-linkcheck.elf']
    samples=[]
    for path in paths:
        e=a.Elf(path);assert e.at(e.symbols['rv_irq_save']['va'],12)==save
        assert e.at(e.symbols['rv_irq_restore']['va'],4)==restore;samples.append(str(path.relative_to(c.ROOT)))
    for parent,names in [(RES/'local/product/candidates',('base','huzi','full')),(RES/'local/probes/candidates',('life','notice','view'))]:
        for name in names:
            path=parent/name/'GXRCE.DAT';raw=path.read_bytes();o,n=struct.unpack_from('>II',raw,132)
            assert raw[o:o+n].count(save+restore)==1;samples.append(str(path.relative_to(c.ROOT)))
    for name in ('full-r8','full-r9'):
        path=RES/'acceptance/local'/name/'GXRCE.DAT';raw=path.read_bytes();o,n=struct.unpack_from('>II',raw,132)
        assert raw[o:o+n].count(save+restore)==1;samples.append(str(path.relative_to(c.ROOT)))
    for path in samples:
        for incoming in range(65536):
            cpu=m.IRQ(incoming);cpu.run(save);assert cpu.psw==incoming&0xffbf and cpu.r[0]==incoming
            cpu.run(restore);assert cpu.psw==incoming
    c.write('irq.json',dict(status='PASS',artifacts=samples,vectors=65536*len(samples),native_execution=False))
    print('PASS IRQ vectors',65536*len(samples),flush=True)

def guard():
    p=load_policy();program=p.Program('final-engine',RES/'acceptance/local/product-r9/m32r-lto/translated.elf')
    class Cpu(p.Cpu):
        def check(self,address,n,kind):
            assert 0x20000000<=address and address+n<=0x22000000
            self.accesses.append((kind,address,n))
    cases=[]
    for source,cap,opened,closed in itertools.product((1,2,3),(0,-1),(0,2,-1),(0,-1)):
        cpu=Cpu(program);cpu.seed(program.symbols['n']+4,0x20720000)
        cpu.seed(0x20720010,0x20710000);cpu.seed(0x20710000+328,source);calls=[]
        def zero(x):
            for i in range(x.r[1]):x.write(x.r[0]+i,0,1)
        def storage(x):
            op,q,r=x.r[2],x.r[3],x.read(x.r[15]);calls.append(op)
            assert op in (1,2,6) and x.r[1]==1
            if op==1:x.write(r+20,7);status=cap
            elif op==2:x.write(r+16,19);status=opened
            else:status=closed
            x.r[0]=status&0xffffffff
            for reg in (1,2,3):x.r[reg]=0xbad00000+reg
        cpu.stubs={program.symbols['ig_zero']:zero,program.symbols['pn_call.isra.0']:storage}
        observed=cpu.run('rejected_card_present')
        expected=0 if source==3 or (cap==0 and opened==2) else 1
        assert observed==expected
        cases.append(dict(source=source,capability=cap,open_status=opened,close_status=closed,blocks_save=observed,storage_ops=calls))
    c.write('guard-machine.json',dict(status='PASS_MODEL_MATCHES_BYTES',cases=cases,
        unavailable_open_allows_save=True,only_read_operations=True,objdump_bytes_verified=program.verified_bytes,native_execution=False))
    print('PASS final guard bytes',len(cases),'cases; RV_UNAVAILABLE permits saving',flush=True)

def resident_host():
    out=c.LOCAL/'resident-host';out.mkdir(exist_ok=True)
    flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-DRV_HOST','-fsanitize=address,undefined',
        '-fno-omit-frame-pointer','-I',RES/'resident']
    sources=[(RES/'resident'/n,False) for n in ('resident.c','loader.c','shared.c','hooks.c','runtime.c','validate_envelope.inc.c')]
    sources += [(RES/'engine_services'/n,True) for n in ('services.c','api.c','runtime.c','crc.c','mark.c','native_seed.c')]
    sources += [(RES/'resident/shared.c',True),(RES/'resident/v3_checks.c',False),(RES/'local/resident/trust.c',False)]
    objects=[]
    for i,(src,service) in enumerate(sources):
        obj=out/(str(i)+'-'+src.stem+'.o');objects.append(obj)
        extra=['-DRV_ENGINE_SERVICES'] if service else []
        if src.name=='runtime.c':extra+=['-Dmemcpy='+('es_test_memcpy' if service else 'rv_test_memcpy'),'-Dmemset='+('es_test_memset' if service else 'rv_test_memset')]
        c.run(['/usr/bin/clang',*flags,*extra,'-c',src,'-o',obj],'resident-host/compile-'+str(i)+'.log')
    binary=out/'checks';c.run(['/usr/bin/clang','-fsanitize=address,undefined',*objects,'-o',binary],'resident-host/link.log')
    log=c.run([binary,RES/'local/resident/fixtures/synthetic-container.fixture'],'resident-host/run.log')
    cases=re.findall(r'^CASE (.+)$',log,re.M);checks=int(re.search(r'PASS_HOST checks=(\d+)',log)[1])
    assert len(cases)==44 and checks==127607
    c.write('resident-host.json',dict(status='PASS',cases=cases,assertions=checks,sanitizers=['ASan','UBSan'],
        mock_engine=True,native_boundaries_doubled=True))
    print('PASS resident host',len(cases),checks,flush=True)

if __name__=='__main__':
    {'ownership':ownership,'constructor':constructor,'replay':replay,'irq':irq,'guard':guard,'resident-host':resident_host}[sys.argv[1]]()
