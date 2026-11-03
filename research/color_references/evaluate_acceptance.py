#!/usr/bin/env python3
"""Score already extracted linear-light ROI means. This never contacts a camera.

CSV: look,scene,repeat,patch_id,group,actual_R/G/B,target_R/G/B,valid.
RGB columns are sRGB-primaries LINEAR LIGHT ROI means in [0,1], not code values.
The reference manifest and acquisition-quality report are required, not inferred.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import numpy as np
from colour_math import SRGB_XYZ,D65,D50,cat,xyz_lab,delta_e00

def stats(v):
    return {'median':float(np.median(v)),'p90':float(np.percentile(v,90)),'max':float(np.max(v))}

def reported_error(values,key):
    value=values.get(key)
    return float(value) if isinstance(value,(int,float)) and np.isfinite(value) and value>=0 else float('inf')

def score(path,reference,quality):
    contract=json.loads((HERE/'acceptance.json').read_text())
    chart=json.loads((HERE/'screen_chart.json').read_text())
    chart_groups={p['id']:{x['id']:x['group'] for x in p['patches']} for p in chart['pages']}
    records=list(csv.DictReader(path.open()))
    failures=[]
    if reference.get('golden_reference_validated') is not True:failures.append('Reference function is not validated on genuine GR pairs')
    for key in ['renderer_sha256','gr_generation','firmware_version','look_settings','sensor_bridge_convention','exposure_scale_frozen']:
        if not reference.get(key):failures.append('Missing reference field: '+key)
    if reference.get('gr_generation') not in contract['reference_generation_candidates']:failures.append('Unselected GR generation')
    referr=reference.get('same_gr_pair_error',{})
    if reported_error(referr,'de00_median')>.5 or reported_error(referr,'de00_p90')>1:failures.append('Reference-renderer error missing or exceeds budget')
    if reference.get('exposure_scale_frozen') is not True:failures.append('Reference exposure scale is not frozen')
    if reference.get('common_white_frozen') is not True:failures.append('Common-illuminant sensor bridge is not frozen')
    for key in ['settings_frozen','raw_headroom_checked','registration_checked','repeatability_checked','no_new_channel_clipping','reference_coverage_checked']:
        if quality.get(key) is not True:failures.append('Acquisition quality missing or failed: '+key)
    if reported_error(quality,'repeatability_de00_p90')>.5:failures.append('Repeatability missing or exceeds 0.5')
    if quality.get('retuned_on_acceptance',True):failures.append('Acceptance used for fitting or no holdout declaration')
    expected={(look,scene,str(rep)) for look in contract['primary_looks'] for scene in ['V1','V2','V3','V4','objects1','objects2'] for rep in [1,2,3]}
    keys={(r['look'],r['scene'],r['repeat']) for r in records}
    if keys!=expected:failures.append('Expected exactly 36 look/scene/repeat frames')
    summaries={};pooled={}
    for key in sorted(keys):
        rr=[r for r in records if (r['look'],r['scene'],r['repeat'])==key]
        ids=[r['patch_id'] for r in rr]
        if len(ids)!=len(set(ids)):failures.append(str(key)+': duplicate patch IDs')
        valid=[r for r in rr if r['valid']=='1']
        is_screen=key[1].startswith('V')
        if is_screen and len(rr)!=48:failures.append(str(key)+': expected all 48 patch records including exclusions')
        if is_screen:
            expected_groups=chart_groups.get(key[1],{})
            if set(ids)!=set(expected_groups):failures.append(str(key)+': patch IDs do not match the frozen chart')
            if any(r['group']!=expected_groups.get(r['patch_id']) for r in rr):failures.append(str(key)+': patch groups do not match the frozen chart')
        minimum=46 if is_screen else 12
        if len(valid)<minimum or len(valid)<.95*len(rr):failures.append(str(key)+': insufficient valid coverage')
        if not valid:continue
        actual=np.array([[float(r['actual_'+c]) for c in 'RGB'] for r in valid]);target=np.array([[float(r['target_'+c]) for c in 'RGB'] for r in valid])
        if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(target)) or np.any(actual<0) or np.any(actual>1) or np.any(target<0) or np.any(target>1):
            failures.append(str(key)+': invalid RGB means');continue
        transform=SRGB_XYZ.T@cat(D65,D50).T
        a=xyz_lab(actual@transform);b=xyz_lab(target@transform);de=delta_e00(a,b)
        pooled.setdefault(key[0],[]).extend(de.tolist())
        report={}
        groups=[('all',np.ones(len(valid),bool),(1.,2.,3.)),('neutral',np.array([r['group']=='neutral' for r in valid]),(.6,1.2,2.))]
        for group in ['memory_skin','memory_sky','memory_foliage']:
            groups.append((group,np.array([r['group']==group for r in valid]),(1.,2.,3.)))
        for group,mask,lim in groups:
            if not mask.any():
                if group=='neutral' or is_screen:failures.append(str(key)+': missing '+group)
                continue
            s=stats(de[mask]);report[group]=s
            if any(s[k]>v for k,v in zip(['median','p90','max'],lim)):failures.append(str(key)+': '+group+' colour threshold')
        neutral=np.array([r['group']=='neutral' for r in valid])
        if not is_screen and neutral.sum()<3:failures.append(str(key)+': fewer than 3 neutral ROIs')
        if neutral.any():
            s=stats(np.abs(a[neutral,0]-b[neutral,0]));report['tone_abs_L']=s
            if any(s[k]>v for k,v in zip(['median','p90','max'],[.5,1.,2.])):failures.append(str(key)+': neutral tone threshold')
            if key[1]=='V1':
                order=np.argsort(b[neutral,0]);L=a[neutral,0][order]
                if np.any(np.diff(L)<-1e-6):failures.append(str(key)+': ramp luminance order reversal')
        summaries['|'.join(key)]=report
    repeatability={}
    for look,scene in sorted({(r['look'],r['scene']) for r in records}):
        maps=[]
        all_ids=[]
        for rep in ['1','2','3']:
            all_ids.append({r['patch_id']:r['group'] for r in records if r['look']==look and r['scene']==scene and r['repeat']==rep})
            maps.append({r['patch_id']:np.array([float(r['actual_'+c]) for c in 'RGB']) for r in records
                         if r['look']==look and r['scene']==scene and r['repeat']==rep and r['valid']=='1'})
        if any(ids!=all_ids[0] for ids in all_ids[1:]):failures.append(look+'/'+scene+': repeat ROI IDs or groups changed')
        common=set.intersection(*(set(x) for x in maps))
        if not common:continue
        vals=[];transform=SRGB_XYZ.T@cat(D65,D50).T
        for i,j in [(0,1),(0,2),(1,2)]:
            a=xyz_lab(np.array([maps[i][k] for k in sorted(common)])@transform)
            b=xyz_lab(np.array([maps[j][k] for k in sorted(common)])@transform)
            vals.extend(delta_e00(a,b))
        s=stats(vals);repeatability[look+'|'+scene]=s
        if s['p90']>.5:failures.append(look+'/'+scene+': measured repeatability exceeds 0.5')
    for look in contract['primary_looks']:
        for rep in ['1','2','3']:
            for group in ['memory_skin','memory_sky','memory_foliage']:
                n=sum(r['look']==look and r['repeat']==rep and r['scene'] in ['objects1','objects2'] and r['group']==group and r['valid']=='1' for r in records)
                if n<3:failures.append(f'{look}/{rep}: real-object {group} has fewer than 3 ROIs')
    return {'status':'PASS_DECLARED_SCREEN_ALIGNMENT' if not failures else 'FAIL_OR_BLOCKED',
        'failures':failures,'frames':len(keys),'per_frame':summaries,'repeatability':repeatability,
        'pooled_equal_patch_by_look':{k:stats(v) for k,v in pooled.items()},
        'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'contract_sha256':hashlib.sha256((HERE/'acceptance.json').read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--reference-manifest',type=Path,required=True);p.add_argument('--quality-report',type=Path,required=True)
    a=p.parse_args();print(json.dumps(score(a.csv,json.loads(a.reference_manifest.read_text()),json.loads(a.quality_report.read_text())),ensure_ascii=False,indent=2))
