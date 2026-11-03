from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
h=a.HERE/'isolated/candidate';fix=a.HERE/'minimal-fix-readonly';rows=[json.loads(x) for x in (h/'local/commands.jsonl').read_text().splitlines()]
layout=json.loads((fix/'build/m32r-lto/size.json').read_text());(fix/'entries.h').write_text(''.join(f'#define OFF_{k.upper()} {v}u\n' for k,v in layout['entries'].items()))
ld=next(x['argv'] for x in reversed(rows) if x['label']=='v34c-link');replacements={}
for stem,source in (('adapter',fix/'adapter.c'),('blackbox',fix/'blackbox.c'),('host_v34c',a.HERE/'readonly_host.c')):
 cc=next(x['argv'] for x in reversed(rows) if x['label'].startswith('v34c-compile-') and any(Path(arg).name==stem+'.c' for arg in x['argv']))
 old=cc[cc.index('-o')+1];obj=fix/(stem+'.o');replacements[old]=str(obj)
 cc=[str(source) if Path(x).name==stem+'.c' else str(obj) if x==old else x for x in cc]
 cc=[('-DACCEPTANCE_ENTRIES_HEADER=\"'+str(fix/'entries.h')+'\"') if x.startswith('-DACCEPTANCE_ENTRIES_HEADER=') else x for x in cc]
 a.run(cc,'readonly-host-compile-'+stem)
binary=fix/'host';ld=[replacements.get(x,x) for x in ld];ld[ld.index('-o')+1]=str(binary);a.run(ld,'readonly-host-link')
results=[]
for unit in range(3):
 p=a.run([binary,unit,fix/'REVIEW_ONLY_NOT_FOR_INSTALL.DAT',h/'local/full-r13/trust.bin',h/'local/full-r13/effective-rows.bin','x','x'],f'readonly-host-{unit}',check=False)
 results.append(dict(unit=unit,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()));print(p.stdout.decode(),p.stderr.decode(),flush=True)
a.dump('minimal-fix-readonly/host-results.json',results)
