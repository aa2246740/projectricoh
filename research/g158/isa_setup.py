"""Reuse final-DAT W probes across all four observed PASM submodes."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
C.setup();C.DATASET='model';C.compute_gate('prepare-PASM-ISA')
s=(C.ROOT/'research/g157/fix_r1_isa_matrix.py').read_text().replace('g157','g158').replace('G157','G158')
s=s.replace("C.LOCAL/'fix-r1/isa'","C.LOCAL/'isa'").replace("C.LOCAL/'fix-r1/fast-isa'","C.LOCAL/'fast-isa'")
s=s.replace("tag=a.profile+'-'+a.unit+'-'+a.backend+", "tag=a.profile+'-'+a.unit+'-'+a.backend+'-PASM'+")
s=s.replace("peer=initial.copy();page=cursor=0;", "put(0x205d9a7f,4,1);put(0x205d9a9f,dial_sub,1);put(S+0x2fc,(0x8010,0x8020,0x8008,0x8800)[dial_sub]);\n    peer=initial.copy();page=cursor=0;")
s=s.replace('row=dict(entry=entry,', 'row=dict(raw_mode=4,submode=dial_sub,N=(0x8010,0x8020,0x8008,0x8800)[dial_sub],entry=entry,')
start=s.index('    for entry in (\'standard\',');end=s.index('\nexcept BaseException:',start)
body=s[start:end];s=s[:start]+"    for dial_sub in range(4):\n"+'\n'.join('    '+line for line in body.splitlines())+s[end:]
(C.HERE/'isa_matrix.py').write_text(s)
jobs=json.loads((C.HERE/'jobs.json').read_text());known={r['id'] for r in jobs}
new=[]
for profile in ('test','release'):
    for backend in ('c','python'):
        key='ISA-'+profile+'-'+backend
        if key in known:continue
        args=['--profile',profile,'--unit','mount','--backend',backend,'--declared-services','--targets','HC+1','--fixture',str(C.LOCAL/'runs'/('fixture-'+profile+'-AUTO')/'service-fixture/manifest.json')]
        new.append(dict(id=key,script='research/g158/isa_matrix.py',args=args,needs=['fixture-'+profile+'-AUTO'],log=str(C.LOCAL/'logs'/(key+'.log'))))
# Keep final-artifact probes ahead of the expensive native catalogue sweeps.
at=next(i for i,r in enumerate(jobs) if r['id'].startswith('sweep-'))
jobs[at:at]=new;C.save(C.HERE/'jobs.json',jobs);print(json.dumps(dict(status='PREPARED',jobs=len(new))))
