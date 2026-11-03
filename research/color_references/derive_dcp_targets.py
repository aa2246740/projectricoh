#!/usr/bin/env python3
"""Evaluate extracted DCP data as a documented reference approximation.

This is not Adobe Camera Raw. Original proprietary tables stay in /tmp.
Only profile summaries and sparse derived probe outputs enter the repository.
"""
from pathlib import Path
import hashlib,json,sys,colorsys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize_scalar
from tiff_read import Tiff
from colour_math import lab_xyz,rgb_lab,xyz_lab,SRGB_XYZ,srgb_encode,srgb_decode,D50,D65,cat,dng_camera_to_xyz,delta_e00

PROPHOTO_XYZ=np.array([[.7976749,.1351917,.0313534],[.2880402,.7118741,.0000857],[0.,0.,.8252100]])
BASE=Path('/tmp/gxr_color_refs/extracted/adobe16_5/CameraRawProfiles.pkg/Payload/CameraProfiles/Camera')

def hsv_table(rgb,table,dims,encoding):
    h,s,v=np.array([colorsys.rgb_to_hsv(*x) for x in np.maximum(rgb,0)]).T
    ve=srgb_encode(v) if encoding==1 else v
    nh,ns,nv=map(int,dims);grid=np.array(table).reshape(nv,nh,ns,3)
    coords=[np.clip(ve,0,1)*(nv-1),(h%1)*nh,np.clip(s,0,1)*(ns-1)]
    lower=[np.floor(x).astype(int) for x in coords];frac=[x-l for x,l in zip(coords,lower)]
    out=np.zeros((len(rgb),3))
    for dv in [0,1]:
        for dh in [0,1]:
            for ds in [0,1]:
                vi=np.minimum(lower[0]+dv,nv-1);hi=(lower[1]+dh)%nh;si=np.minimum(lower[2]+ds,ns-1)
                w=(frac[0] if dv else 1-frac[0])*(frac[1] if dh else 1-frac[1])*(frac[2] if ds else 1-frac[2])
                out+=grid[vi,hi,si]*w[:,None]
    h=(h+out[:,0]/360)%1;s=np.clip(s*out[:,1],0,1);ve=np.clip(ve*out[:,2],0,1)
    v=srgb_decode(ve) if encoding==1 else ve
    return np.array([colorsys.hsv_to_rgb(*x) for x in zip(h,s,v)])

def render_xyz(xyz,tags,ev=0,curve_method='channel_spline'):
    rgb=np.maximum(xyz@np.linalg.inv(PROPHOTO_XYZ).T,0)*2**ev
    if 50938 in tags:
        rgb=hsv_table(rgb,tags[50938],tags[50937],tags.get(51107,[0])[0])
    if 50982 in tags:
        rgb=hsv_table(rgb,tags[50982],tags[50981],tags.get(51108,[0])[0])
    if 50940 in tags:
        pts=np.array(tags[50940]).reshape(-1,2)
        f=CubicSpline(pts[:,0],pts[:,1],bc_type='natural')
        rgb=np.clip(rgb,0,1)
        if curve_method=='channel_spline':rgb=np.clip(f(rgb),0,1)
        else:
            lo=rgb.min(1);hi=rgb.max(1);a=f(lo);b=f(hi)
            s=np.divide(b-a,hi-lo,out=np.zeros_like(a),where=(hi-lo)>1e-12)
            rgb=a[:,None]+(rgb-lo[:,None])*s[:,None]
    xyz=rgb@PROPHOTO_XYZ.T
    linear=xyz@cat(D50,D65).T@np.linalg.inv(SRGB_XYZ).T
    return np.clip(srgb_encode(linear),0,1)

def probes():
    raw=(Path('/tmp/gxr_color_refs/downloads/cc24_after2014/chart.txt')).read_text()
    entries=[]
    for line in raw.splitlines():
        a=line.replace(',','.').split()
        if len(a)==4 and len(a[0])==2 and a[0][0] in 'ABCDEF' and a[0][1] in '1234':
            entries.append({'id':a[0],'set':'ColorChecker24_after2014','Lab_D50':list(map(float,a[1:]))})
    for i,L in enumerate(np.linspace(0,100,33)):entries.append({'id':f'neutral_{i}','set':'neutral_ramp','Lab_D50':[float(L),0,0]})
    chart=json.loads((HERE/'screen_chart.json').read_text())
    for page in chart['pages']:
        for p in page['patches']:
            entries.append({'id':page['id']+':'+p['id'],'set':'nominal_screen_'+page['purpose'],'Lab_D50':p['nominal_display_Lab_D50'],'group':p['group']})
    assert len([p for p in entries if p['set']=='ColorChecker24_after2014'])==24
    return entries

def main():
    probe=probes();xyz=lab_xyz(np.array([p['Lab_D50'] for p in probe]))
    ref=json.loads((HERE/'gr3_reference_measurements.json').read_text());cam=np.array([p['camera_RGB_black_white_normalized'] for p in ref['variants']['standard']['patches']])
    rt=Tiff(Path('/tmp/gxr_color_refs/downloads/bastibe_gr3_dng/Target.DNG').read_bytes()).tags()
    result=[]
    for folder in ['Ricoh GR III','Ricoh GR IIIx']:
        for path in sorted((BASE/folder).glob('*.dcp')):
            data=path.read_bytes();tags=Tiff(data,profile=True).tags();name=tags.get(50936)
            item={'camera_folder':folder,'profile_name':name,'match_name':tags.get(50708),'path_scratch':str(path),
                'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'copyright':tags.get(50942),
                'camera_firmware':None,'input':'Matching camera linear RAW for full profile; derived probes enter normalized XYZ D50 at look stage',
                'output':'approximate display sRGB, SDR, clipping explicitly applied',
                'has_huesat_map':50938 in tags,'has_look_table':50982 in tags,'look_table_dims':tags.get(50981),
                'look_encoding':tags.get(51108,[0])[0],'tone_curve_nodes':len(tags.get(50940,[]))//2,
                'baseline_exposure_offset_ev':tags.get(51109,[0])[0],'default_black_render':tags.get(51110,[0])[0],
                'golden_reference':False,'transform_status':'推断: independent DNG-spec interpretation, not Adobe render or camera JPEG',
                'scope_gaps':['No ACR process-version/default contrast/black rendering emulation','Tone spline boundary/hue preservation interpretation unverified','No real GR IIIx validation pairs'],
                'derived_probes':[]}
            if any(x in (name or '') for x in ['Positive Film','Negative Film','Standard']):
                out=render_xyz(xyz,tags)
                alt=render_xyz(xyz,tags,curve_method='hue_preserving_spline')
                de=delta_e00(rgb_lab(out),rgb_lab(alt))
                item['tone_interpretation_sensitivity_de00']={'median':float(np.median(de)),'p90':float(np.percentile(de,90)),'max':float(de.max())}
                item['derived_probes']=[{**p,'output_srgb':q.tolist(),'output_Lab_D50':l.tolist()} for p,q,l in zip(probe,out,rgb_lab(out))]
                if folder=='Ricoh GR III':
                    mode='positive' if 'Positive' in name else 'negative' if 'Negative' in name else 'standard'
                    merged={**tags,50728:rt[50728],50727:rt[50727]};A,desc=dng_camera_to_xyz(merged)
                    actual=np.array([p['target_srgb'] for p in ref['variants'][mode]['patches']])
                    def objective(ev):
                        pred=render_xyz(cam@A.T,tags,float(ev))
                        return np.mean(delta_e00(rgb_lab(pred[:6]),rgb_lab(actual[:6]))**2)
                    fit=minimize_scalar(objective,bounds=(-2,2),method='bounded')
                    pred=render_xyz(cam@A.T,tags,float(fit.x));de=delta_e00(rgb_lab(pred),rgb_lab(actual))
                    item['same_gr3_chart_comparison']={'exposure_fit_ev':float(fit.x),'scale_fit_on_six_neutrals_only':True,
                        'default_dng_baseline_ev':rt[50730][0],'profile_offset_ev':tags.get(51109,[0])[0],
                        'de00_median':float(np.median(de)),'de00_p90':float(np.percentile(de,90)),
                        'de00_memory_skin_sky_foliage':de[[23,22,21,20]].tolist(),
                        'comparison_is_not_acr_or_profile_quality_test':'Approximate renderer plus global exposure fit; all pipeline assumptions remain exposed'}
            result.append(item)
    output={'schema':'gr-dcp-sparse-probes-v1','package':'Adobe DNG Converter 16.5, extracted only',
        'probe_inputs':'ColorChecker24 After Nov2014 Lab D50 from X-Rite/BabelColor; neutral Lab D50 ramp; original screen design probes',
        'profile_stage_probe_ev':0,'camera_matrix_for_stage_probes':'bypassed intentionally; normalized XYZ D50 look-stage sensitivity only',
        'all_proprietary_tables_kept_outside_repository':True,'profiles':result}
    (HERE/'adobe_gr_profiles.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'profiles':len(result),'derived_colour_profiles':sum(bool(x['derived_probes']) for x in result),
        'GR3_comparisons':{x['profile_name']:x.get('same_gr3_chart_comparison') for x in result if x['camera_folder']=='Ricoh GR III' and x['derived_probes']}},ensure_ascii=False))

if __name__=='__main__':main()
