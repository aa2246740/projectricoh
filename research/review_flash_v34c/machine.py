"""Execute bounded subsets of actual candidate/reference instructions."""
import itertools
import json
from pathlib import Path
import random
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import artifacts as a

OUT=c.LOCAL/'machine'


def add_bytes(p, program, label, raw, va):
    program.spans.append((va,raw))
    text,_=a.disasm(label,raw,va)
    for match in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',text,re.M):
        pc=int(match[1],16);b=bytes.fromhex(match[2])
        if len(b) not in (2,4):continue
        assert b==bytes(program.byte(pc+i) for i in range(len(b)))
        program.width[pc]=len(b)
        program.code[pc]=tuple(program.parse(x) for x in re.split(r' -> | \|\| ',match[3]))


def until(cpu, start, end, bound=1500):
    pc=start;trace=[]
    for _ in range(bound):
        if pc==end:return trace
        assert pc in cpu.p.code,('unexpected external execution',hex(pc))
        trace.append(pc);target=None
        for i,(name,args) in enumerate(cpu.p.code[pc]):
            target=cpu.op(name,args,pc+2*i)
            if target is not None:break
        pc=pc+cpu.p.width[pc] if target is None else target
    raise AssertionError(('instruction limit',hex(pc)))


def cold():
    OUT.mkdir(exist_ok=True)
    p=c.load(c.RES/'policy_machine.py','cold_policy');p.LOCAL=OUT
    official=(c.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    versions={
      'v32':(c.ROOT/'firmware/resident_v32/local/resident/build/resident.elf',c.ROOT/'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'),
      'v33':(c.ROOT/'firmware/resident_v33/local/resident/build/resident.elf',c.ROOT/'firmware/image_v33/local/package_final/SD_ROOT/ilaunch3'),
      'v34c':(c.RES/'local/resident/build/resident.elf',c.PACKAGE/'SD_ROOT/ilaunch3')}
    rows=[];total=0
    for version,(elf,image) in versions.items():
        program=p.Program('cold-'+version,elf);baseline=p.Program('official-displaced-'+version,elf)
        body=image.read_bytes()
        for hook in (2,5,6,7,8,9):
            va,n=a.HOOKS[hook]
            add_bytes(p,program,version+'-H'+str(hook),c.image_at(body,va,n),va)
            add_bytes(p,baseline,'official-H'+str(hook)+'-'+version,c.image_at(official,va,n),va)
        for hook,psw,seed in itertools.product((2,5,6,7,8,9),(0,1,0x40,0x41,0x80,0x81,0xc0,0xc1),range(8)):
            va,n=a.HOOKS[hook];rng=random.Random(seed)
            actual=p.Cpu(program);expected=p.Cpu(baseline)
            regs=[rng.getrandbits(32) for _ in range(16)];regs[0]=0x20730000;regs[14]=p.END;regs[15]=0x2067fffc
            for cpu in (actual,expected):
                cpu.r=regs.copy();cpu.psw=psw
                for at in range(244):cpu.seed(p.ROOT_ADDRESS+at,255,1)
                cpu.seed(0x20730000,0xabcddcba)
            tr=until(actual,va,va+n);until(expected,va,va+n)
            assert actual.r==expected.r and actual.psw==expected.psw,(version,hook,psw,seed)
            # New stores are confined to the temporary save frame below the returned SP.
            for kind,address,size in actual.accesses:
                if kind=='write' and address>=actual.r[15]:
                    assert actual.read(address,size)==expected.read(address,size),(version,hook,hex(address))
                if kind=='write':assert 0x2067f000<=address<=0x2067fffc,(version,hook,'global store',hex(address))
            if seed==0 and psw==0:rows.append(dict(version=version,hook=hook,steps=len(tr),pcs=[hex(v) for v in tr],native_calls=0))
            total+=1
    c.save('cold-machine.json',dict(status='PASS',cases=total,versions=list(versions),hooks=[2,5,6,7,8,9],
           actual_observer_executed=True,observer_not_doubled=True,registers_PSW_SP_equal_official=True,trace_samples=rows,
           H01_excluded_because_it_can_load=True,limits='Cold FF root only; bounded instruction subset, no real IRQ, cache, pipeline, RTOS or complete startup.'))
    print('PASS actual cold stubs + observer against official:',total,'cases')


def inherited():
    OUT.mkdir(exist_ok=True)
    # Reuse the pre-existing bounded instruction interpreter; all output paths are redirected.
    m=c.load(c.RES/'machine_checks.py','review_replay')
    m.LOCAL=OUT/'replay';(m.LOCAL/'resident/build').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(c.RES/'local/resident/build/resident.elf',m.LOCAL/'resident/build/resident.elf')
    shutil.copyfile(c.RES/'local/resident/hooks.json',m.LOCAL/'resident/hooks.json')
    (m.LOCAL/'resident/engine-services').mkdir(exist_ok=True)
    shutil.copyfile(c.RES/'local/resident/engine-services/services-linkcheck.elf',m.LOCAL/'resident/engine-services/services-linkcheck.elf')
    m.replay();m.h07_paths();m.irq_checks()
    ev=c.load(c.RES/'evidence_v34c.py','review_evidence');ev.LOCAL=OUT/'extra'
    ev.LOCAL.mkdir(exist_ok=True)
    ev.loader();ev.constructor();ev.stack()
    c.save('machine-reuse.json',dict(status='PASS',source_scripts=[str(c.RES/'machine_checks.py'),str(c.RES/'evidence_v34c.py')],
           outputs_redirected=True,candidate_not_rebuilt=True,independent_cold_check='cold-machine.json'))


if __name__=='__main__':{'cold':cold,'inherited':inherited}[sys.argv[1]]()
