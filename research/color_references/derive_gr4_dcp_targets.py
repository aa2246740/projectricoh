#!/usr/bin/env python3
"""Derive sparse GR IV profile probes from inert, extracted Adobe data.

No installer or vendor executable runs. This reuses the documented independent
DCP interpreter; its output remains a profile proxy, never a camera golden.
"""
import hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import numpy as np
from derive_dcp_targets import probes,render_xyz
from colour_math import lab_xyz,rgb_lab,delta_e00
from tiff_read import Tiff

def main():
    base=Path('/tmp/gxr_color_refs/extracted/adobe17_5')
    camera_base=base/'CameraRawProfiles.pkg/Payload/CameraProfiles/Camera'
    folders=[p for p in camera_base.iterdir() if p.is_dir() and p.name.casefold()=='ricoh gr iv']
    if len(folders)!=1:raise ValueError('Expected exactly one extracted GR IV camera-profile folder')
    inputs=probes();xyz=lab_xyz(np.array([p['Lab_D50'] for p in inputs]))
    profiles=[];blocks=[]
    for path in sorted(folders[0].glob('*.dcp')):
        data=path.read_bytes();t=Tiff(data,profile=True);tags=t.tags();name=tags.get(50936)
        item={'camera_folder':'Ricoh GR IV','profile_name':name,'match_name':tags.get(50708),
            'package_version':'17.5','path_scratch':str(path),'bytes':len(data),
            'sha256':hashlib.sha256(data).hexdigest(),'copyright':tags.get(50942),'camera_firmware':None,
            'input':'Matching GR IV linear RAW for full profile; sparse probes enter normalized XYZ D50 at look stage',
            'output':'approximate display sRGB, SDR, clipping explicitly applied',
            'has_huesat_map':50938 in tags,'has_look_table':50982 in tags,
            'look_table_dims':tags.get(50981),'look_encoding':tags.get(51108,[0])[0],
            'tone_curve_nodes':len(tags.get(50940,[]))//2,
            'baseline_exposure_offset_ev':tags.get(51109,[0])[0],'default_black_render':tags.get(51110,[0])[0],
            'golden_reference':False,'transform_status':'推断: independent DNG-spec interpretation, not Adobe render or camera JPEG',
            'scope_gaps':['No genuine GR IV RAW/JPEG validation pair acquired',
                'Firmware version and camera slider state not documented by profile',
                'No ACR process-version/default contrast/black rendering emulation',
                'Tone spline hue-preservation interpretation remains unverified'],
            'derived_probes':[]}
        if any(x in (name or '') for x in ['Positive Film','Negative Film','Standard']):
            if 50938 in tags:raise ValueError('GR IV HueSatMap requires an explicit dual-illuminant extension before rendering')
            out=render_xyz(xyz,tags)
            alt=render_xyz(xyz,tags,curve_method='hue_preserving_spline')
            de=delta_e00(rgb_lab(out),rgb_lab(alt))
            item['tone_interpretation_sensitivity_de00']={'median':float(np.median(de)),
                'p90':float(np.percentile(de,90)),'max':float(de.max())}
            item['derived_probes']=[{**p,'output_srgb':q.tolist(),'output_Lab_D50':l.tolist()}
                for p,q,l in zip(inputs,out,rgb_lab(out))]
        profiles.append(item)
        blocks.append({'profile':path.name,'camera_folder':'Ricoh GR IV','blocks':{
            str(k):{'count':entry['count'],'sha256':hashlib.sha256(entry['raw']).hexdigest()}
            for k,entry in t.ifd(t.root).items() if k in [50721,50722,50938,50939,50940,50964,50965,50982]}})
    if not profiles:raise ValueError('No GR IV profiles found')
    result={'schema':'gr-dcp-sparse-probes-v1','package':'Adobe DNG Converter 17.5, extracted only',
        'probe_inputs':'Same 441 canonical/neutral/original-screen probes as adobe_gr_profiles.json',
        'profile_stage_probe_ev':0,'camera_matrix_for_stage_probes':'bypassed intentionally; normalized XYZ D50 look-stage sensitivity only',
        'all_proprietary_tables_kept_outside_repository':True,'profiles':profiles}
    old=json.loads((HERE/'adobe_gr_profiles.json').read_text())
    comparisons=[]
    for p in profiles:
        if not p['derived_probes']:continue
        q=next(x for x in old['profiles'] if x['camera_folder']=='Ricoh GR III' and x['profile_name']==p['profile_name'])
        assert [x['id'] for x in p['derived_probes']]==[x['id'] for x in q['derived_probes']]
        de=delta_e00(np.array([x['output_Lab_D50'] for x in p['derived_probes']]),np.array([x['output_Lab_D50'] for x in q['derived_probes']]))
        comparisons.append({'mode':p['profile_name'],'probe_count':len(de),'de00_median':float(np.median(de)),
            'de00_p90':float(np.percentile(de,90)),'de00_max':float(de.max())})
    result['same_normalized_look_stage_vs_GR3']={'status':'推断: sparse profile-stage differences, not real camera equivalence',
        'camera_matrices_bypassed':True,'comparisons':comparisons}
    (HERE/'adobe_gr4_profiles.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (HERE/'gr4_dcp_block_digests.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2)+'\n')
    comparison=[]
    oldbase=Path('/tmp/gxr_color_refs/extracted/adobe16_5/CameraRawProfiles.pkg/Payload/CameraProfiles/Camera')
    for p in old['profiles']:
        before=Path(p['path_scratch']);after=camera_base/before.relative_to(oldbase)
        digest=hashlib.sha256(after.read_bytes()).hexdigest()
        comparison.append({'profile':before.name,'old_package':'16.5','new_package':'17.5',
            'old_sha256':p['sha256'],'new_sha256':digest,'bytes_identical':p['sha256']==digest})
    (HERE/'dcp_package_comparison.json').write_text(json.dumps({'schema':'adobe-dcp-package-comparison-v1',
        'profiles':comparison},indent=2)+'\n')
    print(json.dumps({'profiles':len(profiles),'names':[p['profile_name'] for p in profiles],
        'derived_colour_profiles':sum(bool(p['derived_probes']) for p in profiles)},ensure_ascii=False))

if __name__=='__main__':main()
