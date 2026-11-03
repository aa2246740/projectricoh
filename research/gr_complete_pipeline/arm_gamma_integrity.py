"""Reverify exported source blocks, listing words, curves and default fields."""
from pathlib import Path
import importlib.util, json, hashlib, re, struct
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('g',ROOT/'arm_gamma_model.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
sha=lambda b:hashlib.sha256(b).hexdigest()
out=json.loads((ROOT/'gr3_gr4_effective_curves.json').read_text());checks=[]
for m,source in out['raw_sources'].items():checks.append({'kind':'payload','model':m,'passed':sha(g.inspect.image(m))==source['sha256']})
for b in out['source_blocks']:
 raw=g.inspect.read(b['model'],int(b['vma'],0),b['size']);checks.append({'kind':'source_block','model':b['model'],'vma':b['vma'],'passed':raw.hex()==b['bytes_hex'] and sha(raw)==b['sha256']})
listings=[]
for p in sorted(ROOT.glob('arm_gamma_*asm.txt')):
 m='gr3' if '_gr3_' in p.name else 'gr4' if '_gr4_' in p.name else None
 if not m:continue
 n=0;bad=[]
 for line in p.read_text().splitlines():
  z=re.match(r'^([0-9a-f]{8}): ([0-9a-f]{8})\s',line)
  if not z:continue
  a,w=map(lambda x:int(x,16),z.groups());observed=g.inspect.u32(m,a);n+=1
  if observed!=w:bad.append({'vma':hex(a),'listing':hex(w),'source':hex(observed)})
 listings.append({'file':p.name,'rows':n,'passed':not bad,'mismatches':bad})
for c in out['effective_curves']:
 vals=g.evaluate_gamma(c['sliders'],c['runtime_gain'],c['model'],c['flag']);checks.append({'kind':'effective_curve','id':c['id'],'passed':vals==c['curve_u16_256'] and sha(struct.pack('<256H',*vals))==c['sha256_u16le']})
defs=out['gr3_initialization_default_field_chain']['fields']
expected={'Standard':[0,0,0,0,0,0,0],'PositiveFilm':[0,0,-1,3,-1,-2,0],'NegativeFilm':[0,0,1,1,0,-1,0],'HighContrastBW':[0,0,0,0,1]}
fields=['Saturation','ColorHue','ImageKey','Contrast','ContrastHighLight','ContrastShadow','Sharpness']
for name,vals in expected.items():
 wanted=fields[2:] if name=='HighContrastBW' else fields
 for suffix,value in zip(wanted,vals):
  key=('AfterRelease' if name=='NegativeFilm' else '')+'StillImageControlNo0Param'+name+suffix
  d=defs[key];word=g.inspect.u32('gr3',int(d['store_vma'],0));initword=g.inspect.u32('gr3',int(d['last_store']['pc'],0))
  checks.append({'kind':'named_default_field','name':key,'passed':d['default_signed_center4']==value and word==int(d['store_word'],16) and initword&0x0ff00000==0x05400000})
math=json.loads((ROOT/'arm_gamma_math_verification.json').read_text());checks.append({'kind':'math_204_a32_formula','passed':math['all_matched'] and math['cases']==204})
summary={'all_passed':all(x['passed'] for x in checks+listings),'checks':len(checks),'listing_rows':sum(x['rows'] for x in listings),'checks_detail':checks,'listings':listings,'files_sha256':{p.name:sha(p.read_bytes()) for p in sorted(ROOT.glob('arm_gamma_*')) if p.is_file() and p.name!='arm_gamma_integrity.json'}}
(ROOT/'arm_gamma_integrity.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in summary.items() if k not in ['checks_detail','listings','files_sha256']})
if not summary['all_passed']:raise SystemExit(1)
