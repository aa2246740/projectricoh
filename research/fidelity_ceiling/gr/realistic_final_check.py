#!/usr/bin/env python3
"""Fast integrity check after the full numerical replay; updates final manifest."""
import os
for _k in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='1'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util
import subprocess
import numpy as np
sp=importlib.util.spec_from_file_location('realistic_compiler',Path(__file__).with_name('realistic_finish.py'))
c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
r,a=c.r,c.a


def same(x,y):
    for key in ('n','median','mean','p90','max'):
        assert abs(x[key]-y[key])<1e-9,(key,x[key],y[key])
    if 'share_below' in y:assert x['share_below']==y['share_below']


if __name__=='__main__':
    a.guard();n=c.ev.source_check();m=a.read(a.HERE/'realistic_metrics.json')
    v=a.load('original_integrity',a.HERE/'verify.py');v.check_public(m)
    prohibited={'node_codes','node_codes_u8','quantized_theta','curves','aux_x','aux_target','chart_target','curve_y'}
    def public(value):
        if isinstance(value,dict):
            for k,x in value.items():assert k not in prohibited,k;public(x)
        elif isinstance(value,list):
            for x in value:public(x)
    public(m)
    cases=0
    for slot,z in m['recipes'].items():
        accepted=r.baseline(slot)
        for iso in ('200','1600'):
            for key,source in (('chart_colour','chart_colour'),('greys','grey'),('loo','loo'),('hue_interpolated_ring','hue_interpolated_ring'),('firmware_ring','synthetic_target_ring')):
                same(z['baselines'][iso]['accepted_round5'][key],accepted['metrics'][iso][source])
        for kind in r.KINDS:
            rec=a.read(r.LOCAL/f'{slot}_{kind}_full.json')
            st=z['models'][kind]['models']['200']
            for key in ('chart_colour','greys','hue_interpolated_ring','firmware_ring'):same(st[key],rec['metrics'][key])
            hold=[]
            for i in range(18):
                rr=a.read(r.LOCAL/f'{slot}_{kind}_fold{i:02d}.json')
                assert rr['fold']==i and rr['history'][-1]['success']
                hold.append(rr['held_out']);cases+=1
            same(a.stats(hold),st['loo'])
            for iso,s in z['models'][kind]['models'].items():
                assert s['plane']['passes'] and s['chain_stock_coordinates']['passes_unclipped'] and s['chain_candidate_coordinates']['passes_unclipped']
            assert rec['min_node_gap_codes']>=2
    assert m['verification']['full_and_fold_cases_rerendered']==228 and m['verification']['maximum_lab_rerender_difference']==0
    result=dict(passed=True,source_inputs_unchanged=n,LOO_statistics_recomputed=cases,full_metrics_match_saved_records=12,accepted_baseline_metrics_match_source=True,public_statistics_only=True,dense_all_final_models_pass=True,grey_failures_preserved=True,camera_acceptance=False)
    a.save(r.LOCAL/'final_check.json',result)
    names=[str(p.relative_to(a.ROOT)) for p in a.LOCAL.rglob('*') if p.is_file()]
    ignored=subprocess.run(['git','check-ignore','--stdin'],cwd=a.ROOT,input='\n'.join(names)+'\n',text=True,stdout=subprocess.PIPE,check=True).stdout.splitlines()
    assert set(names)==set(ignored)
    f=a.load('final_manifest',a.HERE/'finish.py');f.manifest()
    entries=(a.HERE/'SHA256SUMS').read_text().splitlines()
    for row in entries:
        digest,name=row.split('  ',1);assert a.sha(a.HERE/name)==digest,name
    expected={str(p.relative_to(a.HERE)) for p in a.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts}
    assert {row.split('  ',1)[1] for row in entries}==expected
    print(result,'private_ignored',len(names),'SHA256SUMS_verified',len(entries),flush=True)
    for name in ('REALISTIC.md','realistic_metrics.json','REPORT.md','metrics.json','SHA256SUMS'):
        print(a.sha(a.HERE/name),name,flush=True)
