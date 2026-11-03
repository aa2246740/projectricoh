"""Repeat the independent matrix under ASan/UBSan and compare its log bytes."""
from pathlib import Path
import importlib.util
import json
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('driver',HERE/'run_review.py')
r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
r.freeze()
out=HERE/'sanitized';out.mkdir(exist_ok=True)
commands={x['label']:x['argv'] for x in map(json.loads,(r.OUT/'commands.jsonl').read_text().splitlines())}
sub={}
for label,source,extra in (('host-compile-0',HERE/'adversarial.c',[]),('host-compile-2',r.SOURCE/'kernel.c',['-Dp0_kernel=p0_actual_kernel'])):
    cmd=list(commands[label]);old=cmd[cmd.index('-o')+1];obj=out/(Path(old).name)
    cmd[cmd.index('-c')+1]=str(source);cmd[cmd.index('-o')+1]=str(obj);cmd+=extra
    r.run(cmd,'asan-independent-'+label);sub[old]=str(obj)
link=[sub.get(x,x) for x in commands['host-link']];binary=out/'checks';link[link.index('-o')+1]=str(binary)
link.insert(link.index('-o'),str(HERE/'trace/observer.o'));r.run(link,'asan-independent-link')
runs=[]
for gen,fixture in ((113,r.c.FULL),(114,r.c.FULL114)):
    dest=out/str(gen);dest.mkdir(exist_ok=True)
    result=r.run([binary,r.OUT/'GXRCE.DAT',fixture,dest],'asan-independent-run-'+str(gen))
    compared=[]
    for p in sorted((HERE/'trace'/str(gen)).glob('*.BIN')):
        assert (dest/p.name).read_bytes()==p.read_bytes(),p.name;compared.append(p.name)
    runs.append(dict(generation=gen,logs_byte_identical=compared,summary=result.stdout.splitlines()[-1]))
    print(result.stdout.splitlines()[-1])
r.save(HERE/'sanitized-results.json',dict(status='PASS',runs=runs,sanitizers='ASan+UBSan',trace='Separate O0 observer run; this O1 run is uninstrumented.'))
r.freeze()
