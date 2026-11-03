"""Recheck GammaTuning numerical reconstruction against immutable A32 bytes."""
from pathlib import Path
import importlib.util, hashlib, json, itertools, random, struct, time
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('gamma',ROOT/'arm_gamma_model.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
sha=lambda b:hashlib.sha256(b).hexdigest()
cases=[]
# Every slider extreme, low/high gain knees, both flags plus real-reference states.
for model in ['gr3','gr4']:
 for vals in itertools.product([-4,4],repeat=4):
  for gain,flag in [(1024,0),(8192,0),(32768,1)]:cases.append((model,dict(zip(['key','contrast','highlight','shadow'],vals)),gain,flag))
 for name,p in [('standard',{'key':0,'contrast':0,'highlight':0,'shadow':0}),('positive',{'key':-1,'contrast':3,'highlight':-1,'shadow':-2}),('negative',{'key':1,'contrast':1,'highlight':0,'shadow':-1})]:
  for gain in [1024,2048,4096,8192,16384,32768]:cases.append((model,p,gain,0))
 rng=random.Random(20261016)
 for i in range(36):cases.append((model,{k:rng.randrange(-4,5) for k in ['key','contrast','highlight','shadow']},rng.randrange(1024,32769),rng.randrange(2)))
results=[]
for model,p,gain,flag in cases:
 a,info=g.effective_curve(model,**p,gain=gain,flag=flag,details=True);b,trace=g.interpreted_curve(model,**p,gain=gain,flag=flag)
 diffs=[{'index':i,'formula':x,'a32':y} for i,(x,y) in enumerate(zip(a,b)) if x!=y]
 results.append({'model':model,'sliders':p,'gain':gain,'flag':flag,'knee':info['knee_u12'],'formula_a32_equal':not diffs,'mismatches':diffs[:10],'curve_sha256':sha(struct.pack('<256H',*a)),**trace})
 if diffs:print('MISMATCH',results[-1],flush=True)
summary={'cases':len(results),'matched':sum(x['formula_a32_equal'] for x in results),'all_matched':all(x['formula_a32_equal'] for x in results),'results':results,
 'method':'Independent high-level integer formula versus restricted isolated A32 interpreter, not actual camera execution. Both use same immutable original table bytes. Divide hooks implement directly observed UDIV/SDIV operations; unexpected calls and non-synthetic writes reject.'}
(ROOT/'arm_gamma_math_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in summary.items() if k!='results'})
