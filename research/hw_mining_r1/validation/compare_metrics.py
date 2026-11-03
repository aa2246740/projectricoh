#!/usr/bin/env python3
"""Read saved fit outputs and recalculate their published arithmetic only."""
import ast
import hashlib
import json
import re
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
used={}
def read(rel):
    p=ROOT/rel
    raw=p.read_bytes()
    used[rel]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return json.loads(raw)
def save(name,x):
    p=OUT/'evidence'/name
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

gr=read('research/gr4_lut_ceiling/local/isp/summary.json')
for row in gr:
    recomputed=1-row['error']['median']/row['baseline']['median']
    assert abs(recomputed-row['similarity_median'])<1e-12
real=read('research/fidelity_ceiling/fuji/REALISTIC_metrics.json')
real_rows=[]
for slot,r in real['recipes'].items():
    for level,v in r['levels'].items():
        m=v['models']['200']['statistics']
        real_rows.append(dict(slot=slot,level=level,statistics=m))
fuji=read('research/color_fit_v2/fuji_round5/metrics.json')
fuji_rows=[]
for slot,r in fuji['recipes'].items():
    for level,v in r['levels'].items():
        x=v['full_screen']
        for population in ('full_screen','hue_heldout'):
            values=v[population]
            assert abs(1-values['median']/values['stock_median_de00']-values['expected_similarity'])<1e-12
        fuji_rows.append(dict(slot=slot,level=level,full_screen=x,hue_heldout=v['hue_heldout'],
                              chart18_LOO=v['chart18_LOO'],physical_heldout=v['physical_heldout']))
gem=ROOT/'research/hw_mining_r1/gemini'
report=(gem/'REPORT.md').read_text()
scripts=[]
for p in sorted(gem.glob('*.py')):
    raw=p.read_bytes()
    used[str(p.relative_to(ROOT))]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    tree=ast.parse(raw)
    scripts.append(dict(path=str(p.relative_to(ROOT)),
         imports=sorted({n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)} |
                        {n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}),
         numerical_fit_token_lines=[dict(line=no,text=line) for no,line in enumerate(raw.decode().splitlines(),1)
            if re.search(r'least_squares|scipy|curve_fit|minimize\(|DeltaE|delta_e|CIEDE|similarity_median|holdout|heldout',line,re.I)]))
save('metric-comparison.json',dict(
 method='No refit. Parse saved numerical outputs, verify score arithmetic, preserve original populations and caveats.',
 GR_ablation=gr,Fuji_realistic_scope=real['scope'],Fuji_realistic=real_rows,Fuji_round5=fuji_rows,
 Gemini_fit_inventory=scripts,
 Gemini_exact_aggregate_ranges_found={token:token in report for token in ('94–96','94-96','86–92','86-92')},
 target95_remaining_residual_fraction={str(s):1-.05/(1-s) for s in (.87,.83,.52,.66)}))
save('metric-input-hashes.json',used)
print('PASS score arithmetic for',len(gr),'GR ablation rows and',len(fuji_rows),'Fuji fits; read',len(real_rows),'realistic branches; audited',len(scripts),'Gemini scripts for fit evidence')
print('Realistic statistics keys',list(real_rows[0]['statistics']))
print('Gemini exact aggregate ranges present:',{token:token in report for token in ('94–96','94-96','86–92','86-92')})
