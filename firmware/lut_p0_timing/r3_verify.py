"""Rerun reviewer stimuli and trace actual stores in the real host C paths.

LLVM instrumentation observes stores even when the stored value is unchanged.
Fixture setup and the official native constructor run outside the trace window.
"""
import importlib.util
import json
from pathlib import Path
import re
import struct
import zlib

s=importlib.util.spec_from_file_location('r3_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)


def split_arguments(raw):
    depth=0;start=0;args=[]
    for i,char in enumerate(raw):
        if char in '([{<':depth+=1
        elif char in ')]}>':depth-=1
        elif char==',' and not depth:args.append(raw[start:i].strip());start=i+1
    args.append(raw[start:].strip());return args


def pointer_value(arg):
    assert arg.startswith('ptr '),arg
    value=arg[4:]
    while True:
        stripped=re.sub(r'^(?:align \d+|noundef|nonnull|nocapture|noalias|readonly|writeonly)\s+','',value)
        if stripped==value:return value
        value=stripped


def store_size(typed):
    array=re.match(r'^[\[<](\d+) x (.+)[\]>]',typed)
    if array:return int(array[1])*store_size(array[2])
    size={'i8':1,'i16':2,'i32':4,'i64':8,'ptr':8,'float':4,'double':8}.get(typed.split()[0])
    assert size,('unhandled LLVM store type',typed)
    return size


def instrument(source,unit):
    lines=source.read_text().splitlines();out=[];count=0
    for line in lines:
        store=re.match(r'\s*store (?:volatile )?(.+)',line)
        if store:
            args=split_arguments(store.group(1));size=store_size(args[0]);pointer=pointer_value(args[1])
            out.append(f'  call void @p0_trace_store(ptr {pointer}, i64 {size}, i32 {unit})');count+=1
        memory=re.search(r'@(?:llvm\.(?:memcpy|memmove|memset)[^(]*|memcpy|memmove|memset)\(',line)
        if memory and not line.startswith('declare'):
            depth=1;end=memory.end()
            while depth:
                if line[end]=='(':depth+=1
                elif line[end]==')':depth-=1
                end+=1
            args=split_arguments(line[memory.end():end-1]);pointer=pointer_value(args[0]);length=args[2].split()[-1]
            assert args[2].strip().startswith('i64 '),line
            out.append(f'  call void @p0_trace_store(ptr {pointer}, i64 {length}, i32 {unit})');count+=1
        out.append(line)
    out.append('declare void @p0_trace_store(ptr, i64, i32)')
    assert count,('no traced writes',source)
    return '\n'.join(out)+'\n',count


def main():
    c.guard();c.run(['/usr/bin/python3','-I','-B',c.HERE/'freeze.py'],'freeze-before-r3')
    out=c.LOCAL/'r3';out.mkdir(exist_ok=True)
    commands={x['label']:x['argv'] for x in map(json.loads,(c.LOCAL/'commands.jsonl').read_text().splitlines())}
    # Keep this derived from the successful normal verification command set.
    compiles=[]
    i=0
    while 'host-compile-'+str(i) in commands:
        compiles.append(commands['host-compile-'+str(i)]);i+=1
    units=[];objects=[];sites=0
    for i,original in enumerate(compiles):
        command=list(original);source=Path(command[command.index('-c')+1])
        if i==0:source=c.HERE/'r3_checks.c'
        command[command.index('-c')+1]=str(source)
        if source==c.HERE/'kernel.c':command+=['-Dp0_kernel=p0_actual_kernel']
        # The ordinary verification already runs all real C under ASan/UBSan.
        # Here O0 keeps every source store, including same-value assignments.
        command=[x for x in command if x!='-c' and not x.startswith(('-O','-fsanitize=','-fno-sanitize-recover='))]
        command+=['-O0','-fno-vectorize','-fno-slp-vectorize','-S','-emit-llvm']
        ir=out/(str(i)+'.ll');obj=out/(str(i)+'.o')
        command[command.index('-o')+1]=str(ir)
        c.run(command,'r3-ir-'+str(i))
        raw,count=instrument(ir,i);sites+=count
        traced=out/(str(i)+'-traced.ll');traced.write_text(raw)
        c.run(['/usr/bin/clang','-c',traced,'-o',obj],'r3-trace-compile-'+str(i))
        units.append(dict(unit=i,source=str(source.relative_to(c.ROOT)),store_sites=count));objects.append(obj)
    def unit(path,service=False):
        return next(i for i,a in enumerate(compiles) if a[a.index('-c')+1]==str(path) and ('-DRV_ENGINE_SERVICES' in a)==service)
    service=unit(c.S/'services.c',True);shared=unit(c.R/'shared.c');engine_shared=unit(c.R/'shared.c',True)
    observer=out/'observer.o'
    c.run(['/usr/bin/clang','-std=c11','-O1','-Wall','-Wextra','-Werror','-c',c.HERE/'write_trace.c','-o',observer],'r3-observer-compile')
    binary=out/'checks'
    c.run(['/usr/bin/clang',*objects,observer,'-o',binary],'r3-trace-link')
    replacements={}
    for i,original in enumerate(compiles):
        source=Path(original[original.index('-c')+1])
        if i!=0 and source!=c.HERE/'kernel.c':continue
        command=list(original);obj=out/(str(i)+'-asan.o')
        if i==0:command[command.index('-c')+1]=str(c.HERE/'r3_checks.c')
        else:command+=['-Dp0_kernel=p0_actual_kernel']
        command[command.index('-o')+1]=str(obj)
        c.run(command,'r3-asan-compile-'+str(i))
        replacements[original[original.index('-o')+1]]=str(obj)
    asan_binary=out/'checks-asan';link=[replacements.get(x,x) for x in commands['host-link']]
    link[link.index('-o')+1]=str(asan_binary);link.insert(link.index('-o'),str(observer))
    c.run(link,'r3-asan-link')
    runs=[]
    for generation,fixture in ((113,c.FULL),(114,c.FULL114)):
        dest=out/str(generation);dest.mkdir(exist_ok=True)
        asan_dest=out/'asan'/str(generation);asan_dest.mkdir(parents=True,exist_ok=True)
        asan=c.run([asan_binary,c.LOCAL/'GXRCE.DAT',fixture,asan_dest,service,shared,engine_shared,'positive'],'r3-asan-run-'+str(generation))
        assert 'PASS r3 installed='+str(generation) in asan.stdout
        result=c.run([binary,c.LOCAL/'GXRCE.DAT',fixture,dest,service,shared,engine_shared,'positive'],'r3-run-'+str(generation))
        assert 'outside_whitelist=0' in result.stdout and 'PASS r3 installed='+str(generation) in result.stdout
        for log in dest.glob('*.BIN'):assert log.read_bytes()==(asan_dest/log.name).read_bytes(),('trace changed behavior',log)
        runs.append(dict(generation=generation,stdout=result.stdout.strip(),fixture_sha256=c.sha(fixture),
                         sanitizers='ASan+UBSan',asan_stdout=asan.stdout.strip(),asan_trace_logs_byte_identical=True))
        print(result.stdout.strip())
    negative=c.run([binary,c.LOCAL/'GXRCE.DAT',c.FULL114,out,service,shared,engine_shared,'negative'],'r3-negative-store',check=False)
    assert negative.returncode==93 and 'address=2037f3bc' in negative.stderr,negative
    # Preserve the reviewer's mixed-generation loader assertions verbatim.
    mixed_source=c.ROOT/'research/review_lut_p0/mixed_loader.c'
    mixed=out/'mixed_loader.c'
    mixed.write_text(mixed_source.read_text().replace('../../firmware/lut_p0_timing/host_checks.c','host_checks.c'))
    command=list(compiles[0]);command[command.index('-c')+1]=str(mixed)
    mixed_object=out/'mixed_loader.o';command[command.index('-o')+1]=str(mixed_object)
    c.run(command,'r3-mixed-compile')
    link=[str(mixed_object) if x.endswith('/0-host_checks.o') else x for x in commands['host-link']]
    mixed_binary=out/'mixed_loader';link[link.index('-o')+1]=str(mixed_binary)
    c.run(link,'r3-mixed-link')
    mixed_result=c.run([mixed_binary,c.LOCAL/'GXRCE.DAT',c.FULL,c.FULL114],'r3-mixed-run')
    assert mixed_result.stdout.count('PASS mixed')==3
    d=c.load(c.HERE/'decode.py','r3_decoder');decoder=[]
    for generation in (113,114):
        dest=out/str(generation)
        valid=d.decode((dest/'first-publish-retry.BIN').read_bytes(),10)
        assert valid['complete'] and valid['tick_hz']==1000 and valid['reference_start']==100000
        for name in ('reference-interrupted','reference-reopen'):
            try:d.decode((dest/(name+'.BIN')).read_bytes(),10)
            except ValueError as e:decoder.append(dict(generation=generation,case=name,rejected=str(e)))
            else:raise AssertionError('interrupted reference accepted')
        incomplete=d.decode((dest/'admission-over-budget.BIN').read_bytes(),10)
        assert not incomplete['complete'] and incomplete['error']==9 and 'tick_hz' not in incomplete
        partial=d.decode((dest/'partial-bench.BIN').read_bytes(),10)
        assert not partial['complete'] and not partial['error'] and 'tick_hz' not in partial
    review=c.ROOT/'research/review_lut_p0'
    for name in ('first-publish-retry','reference-reopen'):
        try:d.decode((review/(name+'.BIN')).read_bytes(),10)
        except ValueError as e:decoder.append(dict(case='reviewer-r2-'+name,rejected=str(e)))
        else:raise AssertionError('legacy unsafe reference accepted')
    # Reject even a forged complete run carrying the interrupted flag.
    raw=bytearray((out/'114/first-publish-retry.BIN').read_bytes())
    struct.pack_into('>I',raw,2432+36,7)
    struct.pack_into('>I',raw,52,zlib.crc32(raw[128:]));struct.pack_into('>I',raw,124,zlib.crc32(raw[:124]))
    try:d.decode(bytes(raw),10)
    except ValueError as e:decoder.append(dict(case='complete-but-interrupted',rejected=str(e)))
    else:raise AssertionError('forged interrupted DONE accepted')
    c.save(c.LOCAL/'r3-results.json',dict(status='PASS',dat_sha256=c.sha(c.LOCAL/'GXRCE.DAT'),
        runs=runs,decoder=decoder,incomplete_has_tick_hz=False,unchanged_value_negative_control=True,
        store_sites=sites,units=units,model='real resident/probe/gen114 C; LLVM O0 stores traced; native boundaries are host doubles',
        mixed_loader=dict(source_sha256=c.sha(mixed_source),stdout=mixed_result.stdout.strip(),sanitizers='ASan+UBSan'),
        test_sources={str((c.HERE/n).relative_to(c.ROOT)):c.sha(c.HERE/n) for n in ('r3_checks.c','write_trace.c','r3_verify.py')},
        whitelist=['2022F725/1','2022F726/1','2022F5A8/4','2022F5AC/1','tag33 state/4'],
        private_exclusions='host-mapped P0State, resident root, allocated private heap including allocator headers',camera_tested=False))
    c.run(['/usr/bin/python3','-I','-B',c.HERE/'freeze.py'],'freeze-after-r3')
    print('PASS r3 decoder rejects interrupted/legacy references; unchanged-value out-of-whitelist store rejected')


if __name__=='__main__':main()
