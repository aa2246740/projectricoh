"""Fit measured common-curve controls; score final integer rows in memory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,DATA,SCRATCH,BUILD_DATA,digest,dump,check_time,result_path
setup()
import hashlib
import json
import time
import struct
import zlib
import numpy as np
from data import (Cube,Target,xyz_to_encoded,rgb_out,de,stats,scenes,camera_model,
                  creator_jobs,alchemy_jobs)

sys.path.insert(0,str(ROOT/'research/film_look_routes'))
from camera import Camera
from fit import Problem
from convert import samples as old_samples

class SceneRGB(Target):
    def render(self,stock_rgb,xyz=None,info=False):
        out,details=self.cube.apply(xyz_to_encoded(xyz,'srgb'),return_info=True)
        rgb=rgb_out(out,'srgb')*255
        return (rgb,details) if info else rgb

def target_of(job):
    cube=Cube.read(job['path'])
    if job.get('interpretation')=='scene':
        return SceneRGB(cube,'srgb','srgb')
    return Target(cube,job['input'],job['output'])

def score(base,pred,want):
    err=de(pred/255,want/255)
    baseline=de(base/255,want/255)
    den=float(np.median(baseline))
    return {'de00':stats(err),'baseline_de00':stats(baseline),
            'similarity_percent':None if den<.25 else 100*(1-float(np.median(err))/den),
            'label':'电脑预测','absolute_camera_similarity':False,
            'formula':'100 × (1 − median(候选到目标 ΔE00) / median(04 到目标 ΔE00))'}

def old_jobs(dat):
    meta=json.loads((ROOT/'research/looks_g152/local/effects.json').read_text())
    by_name={r['name']:r for r in meta}
    out=[]
    for look in dat.looks:
        row=by_name[look.name]
        path=ROOT/'research/looks_g152/local/luts'/row['source']
        if digest(path)!=row['source_sha256']:
            raise ValueError('Existing Look source differs')
        out.append({'name':look.name,'path':path,'input':'srgb','output':'srgb',
                    'family':'existing','interpretation':row['interpretation'],
                    'entry':look.entry,'base':look.base})
    if len(out)!=10:
        raise ValueError('Expected ten existing Looks')
    return out

def coefficients_entry(dat,q,bw):
    base=3 if bw else 5
    entry=bytearray(dat.entry_of(0,base))
    entry[20:82]=dat.entry_of(0,4)[20:82]
    entry[82:115]=bytes(q['q'][1].tolist())
    entry[216:272]=q['row'].to_bytes()+q['row2'].to_bytes()
    entry[115:211]=bytes(96) if bw else q['colour']
    if bw:
        entry[284:346]=entry[20:82]
        entry[346:379]=entry[82:115]
    entry[456:518]=entry[20:82]
    entry[518:551]=entry[82:115]
    fields=((20,62,8),(82,33,12),(115,96,16),(216,56,212),(284,62,272),
            (346,33,276),(379,66,280),(456,62,448),(518,33,452))
    for at,n,off in fields:
        struct.pack_into('>I',entry,off,zlib.crc32(entry[at:at+n])&0xffffffff)
    return bytes(entry)

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--fresh',action='store_true',help='Recompute every fit instead of resuming saved results')
    fresh=parser.parse_args().fresh
    started=time.monotonic()
    ss=scenes()
    model,dat,provenance=camera_model()
    c=Camera()
    trainx,sw=old_samples(c,700,151)
    n_synthetic_train=len(trainx)
    testx,_=old_samples(c,1400,20261023)
    delta=float(np.max(abs(model.predict(dat.entry_of(0,4),testx)-c.stock(testx))))
    if delta>1e-7:
        raise ValueError('Current Studio and research baseline differ: '+str(delta))
    ref=next((a for a,m in ss if m['unit']=='a12-50'),None)
    xyz_of=lambda x:c.xyz(x,ref['neutral'],ref['matrix'])
    # Fit on three predeclared scenes; fourth scene and all later photos are held out.
    fit_scenes=ss[:3]
    scene_hold=ss[3:]
    for arrays,meta in fit_scenes:
        valid=np.flatnonzero(arrays['valid'])
        take=valid[np.linspace(0,len(valid)-1,140).astype(int)]
        trainx=np.vstack([trainx,arrays['codes'][take]])
        sw=np.r_[sw,np.ones(len(take))]
    trainxyz=np.vstack([xyz_of(trainx[:n_synthetic_train]),
                       *[a['xyz'][np.flatnonzero(a['valid'])[np.linspace(0,int(a['valid'].sum())-1,140).astype(int)]]
                         for a,_ in fit_scenes]])
    if len(trainx)!=len(trainxyz):
        raise ValueError('Training correspondence differs')
    jobs=creator_jobs()+alchemy_jobs()+old_jobs(dat)
    result=json.loads(result_path('look_fits.json').read_text())['fits'] if not fresh and result_path('look_fits.json').exists() else []
    build_rows=json.loads((BUILD_DATA/'all_fitted_effects.json').read_text()) if not fresh and (BUILD_DATA/'all_fitted_effects.json').exists() else []
    parameters=json.loads(result_path('all_fit_parameters.json').read_text())['parameters'] if not fresh and result_path('all_fit_parameters.json').exists() else []
    for job in jobs:
        check_time()
        completed=next((r for r in result if r['name']==job['name'] and r['family']==job['family']),None)
        if completed is not None:
            assert completed['source_sha256']==digest(job['path'])
            print('Retained',job['name'],flush=True)
            continue
        t=time.monotonic()
        target=target_of(job)
        base_train=c.stock(trainx)
        desired=target.render(base_train,trainxyz)
        if job['family']=='existing':
            entry=job['entry']
            fit_info={'method':'existing g152 integer rows, freshly rescored','optimized':False}
        else:
            bw=bool(np.max(np.ptp(desired,axis=1))<.5)
            p=Problem(c,trainx,desired,variant='safe',bw=bw,sample_weights=sw)
            rampx=np.repeat(c.curve.xs[:,None],3,axis=1)
            ramp=target.render(c.stock(rampx),xyz_of(rampx))
            initial=p.theta0.copy()
            initial[p.qstart:p.t2start]=np.maximum.accumulate(ramp@np.array([.299,.587,.114]))-c.curve.ys
            fit,solver=p.solve(initial,100)
            q=p.quantize(fit.x)
            entry=coefficients_entry(dat,q,bw)
            fit_info={'method':'g152 safe common curve + matrix Y mix + 24 symmetric sectors',
                      'optimized':True,'solver':solver,'bw':bw,'quantized_before_scoring':True,
                      'curve_values':q['q'][1].tolist(),'theta':q['theta'].tolist(),
                      'sector_safety':q['safety'],
                      'fitted_rows_sha256':hashlib.sha256(entry[82:115]+entry[115:211]+entry[216:272]).hexdigest()}
            short={'千禧回声 A':'QianXi A','千禧回声 B':'QianXi B',
                   'Phocus Standard':'Phocus STD','Phocus Nature':'Phocus NTR',
                   'ARRI Classic709':'ARRI 709','Classic Chrome':'Classic Chr',
                   'RED Film Bias':'RED FilmBias','Leica Classic':'Leica Cls'}.get(job['name'],job['name'])
            assert 1<=len(short.encode('ascii'))<=12
            build_row={'name':short,'base':3 if bw else 5,'mask':7,'entry_hex':entry.hex(),
                       'source_sha256':digest(job['path']),'source':str(job['path'].relative_to(ROOT)),
                       'interpretation':'after04' if job['input']=='srgb' else 'scene-vlog',
                       'license':'local evaluation only','attribution':'',
                       'evidence':'电脑预测；MOUNT 与 28mm 为50mm模型迁移，未标定'}
            build_rows.append(build_row)
            parameters.append({'name':short,'display_name':job['name'],'family':job['family'],
                'base':build_row['base'],'unit_mask':7,'curve_hex':entry[82:115].hex(),
                'matrix_hex':entry[216:272].hex(),'colour_hex':entry[115:211].hex(),
                'fitted_rows_sha256':fit_info['fitted_rows_sha256'],
                'entry_sha256':hashlib.sha256(entry).hexdigest(),
                'source_sha256':digest(job['path']),'source':str(job['path'].relative_to(ROOT)),
                'input':job['input'],'output':job['output']})
        row={'name':job['name'],'family':job['family'],'source':str(job['path'].relative_to(ROOT)),
             'source_sha256':digest(job['path']),'input':job['input'],'output':job['output'],
             'interpretation':job.get('interpretation','declared'), 'fit':fit_info,'units':{}}
        for ui,unit in enumerate(('a12-50','a12-28','mount-a12')):
            unit_model, _, _ = camera_model(ui)
            base=unit_model.predict(dat.entry_of(ui,4),testx,bw_chroma='zero')
            want=target.render(base,xyz_of(testx))
            pred=np.rint(unit_model.predict(entry,testx,bw_chroma='zero'))
            synthetic_score=score(base,pred,want)
            photo_scores=[]
            for arrays,meta in scene_hold:
                if meta['unit']!=unit:
                    continue
                valid=np.flatnonzero(arrays['valid'])
                take=valid[np.linspace(0,len(valid)-1,min(2500,len(valid))).astype(int)]
                x=arrays['codes'][take]
                base=unit_model.predict(dat.entry_of(ui,4),x,bw_chroma='zero')
                want=target.render(base,arrays['xyz'][take])
                pred=np.rint(unit_model.predict(entry,x,bw_chroma='zero'))
                photo_scores.append({'path':meta['path'],'iso':meta['iso'],
                                     **score(base,pred,want)})
            # Pooled holdout has equal maximum sample count per photo.
            if photo_scores:
                bs=[];ps=[];ts=[]
                for arrays,meta in scene_hold:
                    if meta['unit']!=unit: continue
                    valid=np.flatnonzero(arrays['valid'])
                    take=valid[np.linspace(0,len(valid)-1,min(2500,len(valid))).astype(int)]
                    x=arrays['codes'][take]
                    b=unit_model.predict(dat.entry_of(ui,4),x,bw_chroma='zero')
                    bs.append(b);ps.append(np.rint(unit_model.predict(entry,x,bw_chroma='zero')))
                    ts.append(target.render(b,arrays['xyz'][take]))
                pooled=score(np.vstack(bs),np.vstack(ps),np.vstack(ts))
            else:
                pooled=None
            row['units'][unit]={'model_scope':'50mm ISO200 标定模型' if ui==0 else '50mm 模型迁移，未标定',
                                'synthetic_reference_colour':'50mm DNG matrix and fixed middle-grey anchor',
                                'synthetic_holdout':synthetic_score,'photo_holdout':pooled,'photos':photo_scores,
                                'camera_acceptance':'未定'}
        row['seconds']=time.monotonic()-t
        result.append(row)
        BUILD_DATA.mkdir(parents=True,exist_ok=True)
        (BUILD_DATA/'local').mkdir(exist_ok=True)
        creator_build=[x for x in build_rows if 'panasonic-25th-luts-20261102' in x['source']]
        (BUILD_DATA/'local/effects.json').write_text(json.dumps(creator_build,ensure_ascii=False,indent=2)+'\n')
        (BUILD_DATA/'all_fitted_effects.json').write_text(json.dumps(build_rows,ensure_ascii=False,indent=2)+'\n')
        dump('lumix_fit_parameters.json',{'schema':'gxr-look-fit-parameters/1','donor':provenance,
             'parameters':[p for p in parameters if p['family']=='creator'],
             'builder_input':str((BUILD_DATA/'local/effects.json').relative_to(ROOT)),
             'product_files_written':False,'physical_acceptance':'未定'})
        dump('all_fit_parameters.json',{'schema':'gxr-look-fit-parameters/1','donor':provenance,
                                        'parameters':parameters})
        dump('look_fits.json',{'provenance':provenance,'baseline_model_max_difference':delta,
            'train_photos':[m['path'] for _,m in fit_scenes],
            'holdout_photos':[m['path'] for _,m in scene_hold], 'synthetic_train':n_synthetic_train,
            'synthetic_holdout':len(testx),'max_nfev':100,'fits':result})
        print(job['name'],job['family'],'50mm synthetic',
              row['units']['a12-50']['synthetic_holdout']['similarity_percent'],
              'photo',row['units']['a12-50']['photo_holdout']['similarity_percent'],flush=True)
    print('Fits complete',len(result),'seconds',time.monotonic()-started,flush=True)

if __name__=='__main__':
    main()
