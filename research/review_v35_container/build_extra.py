from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
h=a.HERE/'isolated/candidate';out=h/'local/v34c-host'
rows=[json.loads(x) for x in (h/'local/commands.jsonl').read_text().splitlines()]
source=str(h/'host_v34c.c')
compile=next(x['argv'] for x in reversed(rows) if x['label'].startswith('v34c-compile-') and source in x['argv'])
link=next(x['argv'] for x in reversed(rows) if x['label']=='v34c-link')
old=compile[compile.index('-o')+1];obj=str(a.HERE/'extra_host.o');binary=str(a.HERE/'extra_host')
a.run([str(a.HERE/'extra_host.c') if x==source else obj if x==old else x for x in compile],'extra-compile')
link=[obj if x==old else x for x in link];link[link.index('-o')+1]=binary
a.run(link,'extra-link')
results=[]
for unit in range(3):
 p=a.run([binary,'review-extra',unit,h/'local/full-r13/GXRCE.DAT',h/'local/full-r13/trust.bin',h/'local/full-r13/effective-rows.bin',a.ROOT/'firmware/engine_v36_r28/candidate/local/full-r13/GXRCE.DAT','0'],f'extra-unit-{unit}',check=False)
 results.append(dict(unit=unit,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
 print(p.stdout.decode()[-1800:],p.stderr.decode(),flush=True)
a.dump('extra-results.json',results)
