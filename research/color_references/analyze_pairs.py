#!/usr/bin/env python3
"""Independent, read-only paired-RAW measurements. All outputs stay in this folder."""
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import numpy as np
from PIL import Image
from scipy.interpolate import PchipInterpolator
from scipy.spatial import Delaunay
from colour_math import dng_camera_to_xyz,rgb_lab,delta_e00,D50,lab_xyz
from tiff_read import Tiff,jpeg_exif,exif_summary,unpack_raw,raw_ifd,cfa_roi,crop_info

def save(name,d):
    (HERE/name).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def ident(p):
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def blocks(x,n):
    h,w=x.shape[:2];h-=h%n;w-=w%n;x=x[:h,:w]
    return x.reshape(h//n,n,w//n,n,*x.shape[2:]).mean(axis=(1,3))

def sample_full(t,raw,d,jpeg,n=32):
    ox,oy,cw,ch=crop_info(d)
    if jpeg.shape[:2]!=(ch,cw):raise ValueError('JPEG dimensions do not match DefaultCrop')
    raw=raw[oy:oy+ch,ox:ox+cw]
    pattern=np.frombuffer(d[33422]['raw'],np.uint8).reshape(2,2)
    channels=[[] for _ in range(3)]
    for dy in range(2):
        for dx in range(2):
            c=pattern[(oy+dy)%2,(ox+dx)%2]
            channels[c].append(blocks(raw[dy::2,dx::2].astype(float),n//2))
    camera=np.stack([np.mean(c,axis=0) for c in channels],-1)
    black=float(np.mean(d.get(50714,{'value':[0]})['value']));white=d[50717]['value'][0]
    return (camera-black)/(white-black),blocks(jpeg,n),[ox,oy,cw,ch],black,white

def metric(pred,actual):
    de=delta_e00(rgb_lab(np.clip(pred,0,1)),rgb_lab(actual))
    return {'patches':len(actual),'de00_median':float(np.median(de)),'de00_p90':float(np.percentile(de,90)),
            'rgb8_rmse':float(np.sqrt(np.mean((pred-actual)**2))*255)}

def features(x,degree):
    if degree==1:return np.column_stack([np.ones(len(x)),x])
    r,g,b=x.T
    return np.column_stack([np.ones(len(x)),r,g,b,r*r,g*g,b*b,r*g,r*b,g*b])

def fit_poly(x,y,degree):
    a=features(x,degree)
    reg=np.eye(a.shape[1])*1e-5;reg[0,0]=0
    return np.linalg.solve(a.T@a+reg,a.T@y)

def gr_reference():
    source=Path('/tmp/gxr_color_refs/downloads/bastibe_gr3_dng/Target.DNG')
    t=Tiff(source.read_bytes());d=raw_ifd(t)
    cache=Path('/tmp/gxr_color_refs/extracted/gr3/raw.npy')
    cache_record=cache.with_suffix('.json')
    source_sha=hashlib.sha256(t.data).hexdigest()
    valid_cache=False
    if cache.exists() and cache_record.exists():
        r=json.loads(cache_record.read_text())
        valid_cache=r.get('dng_sha256')==source_sha and r.get('cache_sha256')==hashlib.sha256(cache.read_bytes()).hexdigest()
    if valid_cache:raw=np.load(cache)
    else:
        raw,d=unpack_raw(t);cache.parent.mkdir(parents=True,exist_ok=True);np.save(cache,raw)
        cache_record.write_text(json.dumps({'dng_sha256':source_sha,'cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest()})+'\n')
    A,desc=dng_camera_to_xyz(t.tags())
    prior=json.loads((ROOT/'research/color_calibration/reference_analysis.json').read_text())
    ox,oy,cw,ch=crop_info(d);black=float(np.mean(d[50714]['value']));white=d[50717]['value'][0]
    camera=[];rois=prior['chart_rois']
    for row in rois:
        b=np.array(row['box_xyxy'])+np.array([ox,oy,ox,oy])
        camera.append((cfa_roi(t,raw,d,b)-black)/(white-black))
    camera=np.array(camera)
    xyz=camera@A.T
    result={'source_dng':ident(source),'dng_metadata':exif_summary(t),'dng_matrices':desc,
        'crop_raw_xywh':[ox,oy,cw,ch],'black':black,'white':white,
        'decoder':'original restricted SOF3 decoder; system FFmpeg rejected two-component lossless JPEG as not implemented; independent decoder confirmation unavailable',
        'roi_provenance':'Read-only reuse of prior chart-centre coordinates; remeasured RAW and JPEG pixels independently',
        'model_status':'24 chart patches under one illumination; no validated general GR reference function',
        'variants':{}}
    rows=[]
    for mode in ['standard','positive','negative']:
        path=Path('/tmp/gxr_color_refs/downloads')/('bastibe_gr3_'+mode)/(mode+'.JPG')
        image=np.asarray(Image.open(path).convert('RGB'),float)/255
        jpeg=[];st=[]
        for box in rois:
            x0,y0,x1,y1=box['box_xyxy'];q=image[y0:y1,x0:x1]
            jpeg.append(q.mean((0,1)));st.append(q.std((0,1)))
        jpeg=np.array(jpeg);output_lab=rgb_lab(jpeg)
        m=exif_summary(jpeg_exif(path.read_bytes()))
        models={}
        for degree in [1,2]:
            pred=np.empty_like(jpeg)
            for k in range(24):
                mask=np.arange(24)!=k
                B=fit_poly(camera[mask],jpeg[mask],degree)
                pred[k]=features(camera[k:k+1],degree)@B
            B=fit_poly(camera,jpeg,degree)
            models[str(degree)]={'basis':'constant + raw RGB' if degree==1 else 'constant + raw RGB + six second-order products',
                'coefficients':B.tolist(),'leave_one_patch_out':metric(pred,jpeg),
                'training':metric(features(camera,degree)@B,jpeg),'golden_reference':False}
        item={'source_jpeg':ident(path),'metadata':m,'patches':[], 'experimental_models':models}
        for k,box in enumerate(rois):
            name=box['label'];group='neutral' if name.startswith('D') else ('memory_skin' if name in ['A1','A2'] else 'memory_sky' if name=='A3' else 'memory_foliage' if name=='A4' else 'colour')
            p={'chart_label':name,'group':group,'jpeg_roi_xyxy':box['box_xyxy'],
                'camera_RGB_black_white_normalized':camera[k].tolist(),'relative_XYZ_D50_from_tags':xyz[k].tolist(),
                'target_srgb':jpeg[k].tolist(),'target_Lab_D50':output_lab[k].tolist(),'jpeg_std':st[k].tolist()}
            item['patches'].append(p)
            rows.append({'mode':mode,'patch':name,'group':group,**{f'camera_{c}':camera[k,i] for i,c in enumerate('RGB')},
                **{f'jpeg_{c}':jpeg[k,i] for i,c in enumerate('RGB')},**{f'target_{c}':output_lab[k,i] for i,c in enumerate(['L','a','b'])}})
        neutral_y=xyz[:6,1]
        order=np.argsort(neutral_y);x=neutral_y[order];q=jpeg[:6][order]
        ramp=np.linspace(x[0],x[-1],33)
        out=np.column_stack([PchipInterpolator(x,q[:,i])(ramp) for i in range(3)])
        item['neutral_ramp_derived']={'source':'PCHIP through six observed neutral patches only; interpolation, no extrapolation',
            'relative_XYZ_Y':ramp.tolist(),'target_srgb':out.tolist(),'target_Lab_D50':rgb_lab(out).tolist()}
        result['variants'][mode]=item
    with (HERE/'gr3_chart_targets.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save('gr3_reference_measurements.json',result)
    return A,result

def gxr_pairs(Agr):
    paths=[ROOT/'captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.DNG']
    paths+=sorted((ROOT/'captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH').glob('R805113[0-7].DNG'))
    result=[];outrows=[]
    for path in paths:
        t=Tiff(path.read_bytes());raw,d=unpack_raw(t);A,desc=dng_camera_to_xyz(t.tags())
        jp=path.with_suffix('.JPG');image=np.asarray(Image.open(jp).convert('RGB'),float)/255
        x,y,crop,black,white=sample_full(t,raw,d,image)
        shape=x.shape[:2];x=x.reshape(-1,3);y=y.reshape(-1,3);lab=rgb_lab(y)
        valid=(x.min(1)>.005)&(x.max(1)<.98)&(y.min(1)>1/255)&(y.max(1)<254/255)
        chroma=np.hypot(lab[:,1],lab[:,2]);s=np.linalg.svd(x[valid]-x[valid].mean(0),compute_uv=False) if valid.sum()>3 else np.array([0,0,0])
        item={'dng':ident(path),'jpeg':ident(jp),'metadata_dng':exif_summary(t),'metadata_jpeg':exif_summary(jpeg_exif(jp.read_bytes())),
            'crop_raw_xywh':crop,'matrix':desc,'sensor_bridge_to_bastibe_GR3':(np.linalg.inv(Agr)@A).tolist(),
            'as_shot_bridge_role':'Diagnostic only: each side has its own WB adaptation. Acceptance uses common_white_sensor_bridges.json instead.',
            'raw_clip_fraction':float(np.mean(raw>=white)),'patches_32x32':len(x),'valid_patches':int(valid.sum()),
            'jpeg_chroma_p50_p95_max':np.percentile(chroma,[50,95,100]).tolist(),'jpeg_chroma_gt10_fraction':float(np.mean(chroma>10)),
            'raw_centered_singular_values':s.tolist(),'raw_condition_number':float(s[0]/s[-1]) if s[-1]>0 else None,
            'measurement_status':'已验证: paired pixels and metadata; 推断: DNG matrix bridge; unknown: absolute reflective colour error'}
        if valid.sum()>50:
            fold=np.repeat(np.arange(shape[1])[None,:],shape[0],axis=0).reshape(-1)//max(1,int(np.ceil(shape[1]/4)))
            pred=[];actual=[]
            for k in range(4):
                tr=valid&(fold!=k);te=valid&(fold==k)
                if tr.sum()<20 or te.sum()<1:continue
                B=fit_poly(x[tr],y[tr],2);pred.append(features(x[te],2)@B);actual.append(y[te])
            item['within_frame_spatial_holdout_polynomial']=metric(np.concatenate(pred),np.concatenate(actual))
            item['holdout_is_not_colour_accuracy']='Same image vertical-strip holdout; scene, ISO and look vary between files. No calibrated control response follows.'
        if path.stem in ['R8051129','R8051136','R8051137']:
            for i in np.flatnonzero(valid)[::4]:
                outrows.append({'shot':path.stem,'patch':int(i),**{f'camera_{c}':x[i,k] for k,c in enumerate('RGB')},
                    **{f'jpeg_{c}':y[i,k] for k,c in enumerate('RGB')},**{f'xyzD50_{c}':(A@x[i])[k] for k,c in enumerate('XYZ')}})
        result.append(item)
    with (HERE/'gxr_paired_samples.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(outrows[0]));w.writeheader();w.writerows(outrows)
    save('gxr_characterisation.json',{'schema':'gxr-camera-matrix-and-pairs-v1','pairs':result,
        'control_response_identified':False,'brand_fit_residuals':None,'validity_rule':'RAW channel means in (.005,.98), JPEG means in (1/255,254/255); no nominal screen Lab assumed',
        'jpeg_block_means':'Encoded JPEG means; a modelling statistic. Acceptance averages per-pixel linear-light RGB before Lab, as described in REPORT.',
        'gxr_whitebalance_axes_from_makernote':None})
    return result

if __name__=='__main__':
    A,ref=gr_reference();gxr=gxr_pairs(A)
    print(json.dumps({'gr3_software':{k:v['metadata']['software'] for k,v in ref['variants'].items()},
        'gr3_leave_patch_out':{k:v['experimental_models']['2']['leave_one_patch_out'] for k,v in ref['variants'].items()},
        'gxr_pairs':len(gxr),'matrices_derived':len(gxr)+1},ensure_ascii=False))
