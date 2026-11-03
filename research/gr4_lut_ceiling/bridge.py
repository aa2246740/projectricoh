"""Matrix transport sensitivity, measured renderer residuals, and daily evidence."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,feature,PAIRS
import argparse
import csv
from PIL import Image


def dng_module():
    mod=rt.module('ceiling_dng','research/color_table_fit/dng_scene.py')
    rt.inp('research/color_calibration/analyze_capture.py')
    session=rt.module('ceiling_session','research/chart_session_20261024/session_runtime.py')
    session.patch_tiff(mod.analyze_capture().Tiff)
    return mod


def gxr_tags(path,mod):
    t=mod.analyze_capture().Tiff(rt.inp(path).read_bytes())
    root=t.ifd(t.root)
    candidates=[root]+[t.ifd(o) for o in root.get(330,{}).get('value',[])]
    raw=next(r for r in candidates if r.get(262,{}).get('value',[None])[0]==32803)
    return {k:v['value'] for k,v in {**root,**raw}.items()}


def matrices():
    from isp import model
    m=model();mod=dng_module()
    gx=gxr_tags('captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG',mod)
    # Select a raw source from the original template receipt, not from its name.
    source=rt.read('research/gr_dense_reference/local/private/gr4/r3/inputs.json')
    tiff=rt.module('ceiling_tiff','research/gr_incamera_dev/tiff_io.py')
    original=rt.ROOT/'captures/contrib/2026-10-19/gr4-modes/positive.DNG'
    gr=tiff.Tiff(rt.inp(original).read_bytes()).tags()
    B,info=rt.cm.common_white_sensor_bridge(gx,gr)
    def transport(temperature):
        mg,_=rt.cm.camera_matrix_at_temperature(gx,temperature)
        mr,_=rt.cm.camera_matrix_at_temperature(gr,temperature)
        ng,nr=mg@rt.cm.D65,mr@rt.cm.D65
        ng,nr=ng/ng[1],nr/nr[1]
        T=np.diag(1/nr)@mr@np.linalg.inv(mg)@np.diag(ng)
        return T/(T@np.ones(3))[1]
    results=[]
    for slot,style in [('01','positive'),('02','negative')]:
        d=Dense(style);a=rt.arrays(PAIRS[style]+'/local/fit/data.npz')
        x=a['scene_x'];base=m.predict('04',x);baseline=rt.lab(base)
        original_target,valid,_=d.target(x,baseline)
        changes=[]
        for temperature in (2856.,3500.,5000.,6504.,10000.):
            T=transport(temperature)
            pred,support,_=d.raw_function(feature(x@T.T*(d.anchor/320)))
            from style import relative
            target=relative(baseline,pred[:,:3],pred[:,3:])
            use=valid & support & a['supported']
            error=rt.cm.delta_e00(target[use],original_target[use])
            changes.append(dict(temperature=temperature,n=int(use.sum()),target_shift=rt.stats(error),
                                matrix=T,not_a_measured_bridge_error=True))
        denominator=rt.cm.delta_e00(rt.lab(a['base_rgb'][a['supported']]),a['new_target'][a['supported']])
        allowed=rt.stats(denominator)
        allowed={key:.05*value if key!='n' else value for key,value in allowed.items()}
        results.append(dict(slot=slot,illumination_sensitivity=changes,
                            threshold_95_percent=allowed,baseline_to_target=rt.stats(denominator)))
    rt.dump('bridge/matrices.json',dict(GXR_forward_matrix_present=50964 in gx or 50965 in gx,
                GRIV_forward_matrix_present=50964 in gr or 50965 in gr,
                GXR_color_matrix_tags=[k for k in (50721,50722,50723,50724,50727,50778,50779) if k in gx],
                GRIV_color_matrix_tags=[k for k in (50721,50722,50723,50724,50727,50778,50779) if k in gr],
                common_white_bridge=info,results=results,matched_cross_camera_scenes=0,
                bridge_error_identifiable=False,spectral_sensitivities_available=False))
    print('matrices: forward matrices',50964 in gx or 50965 in gx,50964 in gr or 50965 in gr,
          '95% error budgets',[(r['slot'],r['threshold_95_percent']['median']) for r in results],flush=True)


def native():
    from isp import model,modules
    m=model();mod=dng_module();_,cal,_,_=modules()
    calibration=rt.read('research/refit_50mm_r7/local/folds/full/calibration.json')
    ar=rt.module('ceiling_native_metadata','research/hue_ring/analyze_ring.py')
    session=rt.module('ceiling_native_session','research/chart_session_20261024/session_runtime.py')
    session.patch_tiff(ar.s2d().Tiff)
    folder=rt.ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH'
    out=[]
    for number in (1476,1477):
        stem=f'R805{number:04d}';jp=rt.inp(folder/(stem+'.JPG'));dp=rt.inp(folder/(stem+'.DNG'))
        with Image.open(jp) as im:
            image=np.asarray(im.convert('RGB'));orientation=im.getexif().get(274,1)
        d=mod.Dng(dp);h,w=image.shape[:2];mapping=mod.RawMap(d,(w,h),orientation)
        metadata=ar.read_meta(jp,dp,None)
        verification=mod.verify_mapping(d,image,mapping)
        if verification.get('ok'):
            off=verification['suggested_integer_offset_xy']
            assert max(abs(v) for v in off)<=8
            mapping=mod.RawMap(d,(w,h),orientation,off)
        xx,yy=np.meshgrid(np.linspace(48,w-49,40).astype(int),np.linspace(48,h-49,28).astype(int))
        centers=np.c_[xx.ravel(),yy.ravel()];dx,dy=np.meshgrid(np.arange(-6,6),np.arange(-6,6))
        xs=centers[:,0,None]+dx.ravel()[None,:];ys=centers[:,1,None]+dy.ravel()[None,:]
        block=image[ys,xs].astype(float);observed=block.mean(1);jsd=block.std(1)
        cy,cx=mapping.pixels(ys,xs);y0,x0,_,_=d.crop_window()
        pixels=d.normalised_at(cy+y0,cx+x0);cfa=d.cfa_at(cy+y0,cx+x0)
        raw=np.column_stack([np.sum(np.where(cfa==k,pixels,0),axis=1)/np.sum(cfa==k,axis=1) for k in range(3)])
        maximum=np.column_stack([np.max(np.where(cfa==k,pixels,-1),axis=1) for k in range(3)])
        sd=np.column_stack([np.sqrt(np.sum(np.where(cfa==k,(pixels-raw[:,k,None])**2,0),axis=1)/np.sum(cfa==k,axis=1)) for k in range(3)])
        valid=(maximum<.98).all(1)&(raw>.0005).all(1)&(observed>3).all(1)&(observed<252).all(1)&(jsd.max(1)<10)&(sd.max(1)<.025)
        rawwb=raw/d.as_shot_neutral;x=cal.apply_calibration(rawwb,calibration)
        prediction=m.predict('04',x)
        error=rt.cm.delta_e00(rt.lab(prediction[valid]),rt.lab(observed[valid]))
        np.savez_compressed(rt.LOCAL/f'bridge/{stem}.npz',raw=raw,raw_wb=rawwb,x=x,observed=observed,
                            prediction=prediction,valid=valid,centers=centers,error=error,jpeg_sd=jsd,raw_sd=sd)
        out.append(dict(id=stem,iso=d.exif.get('iso'),orientation=orientation,points=int(valid.sum()),
                        mapping=verification,stock_row5_model_error=rt.stats(error),
                        raw13=metadata['raw13'],display=metadata['display'],
                        matches_calibrated_menu_state=metadata['raw13']==calibration['selector_bytes_04']['raw13'],
                        camera04_identity='task-provided native pair; no live camera accessed',
                        renderer_residual_not_cross_camera_bridge=True))
        print('native',stem,d.exif.get('iso'),int(valid.sum()),rt.stats(error),flush=True)
    rt.dump('bridge/native.json',out)


def daily():
    from isp import model,modules
    m=model();_,cal,_,_=modules()
    path=rt.inp('research/daily_bugs_20261024/local/frames.csv')
    rows=list(csv.DictReader(path.read_text().splitlines()))
    source=rt.ROOT/'research/daily_bugs_20261024/local/samples'
    calibration=rt.read('research/refit_50mm_r7/local/folds/full/calibration.json')
    out=[];errors=[];base04=[];targetcoverage={s:[] for s in ('positive','negative')}
    dense={s:Dense(s) for s in ('positive','negative')}
    for row in rows:
        name=row['frame'];sample=source/(name+'.npz')
        if not sample.exists():continue
        a=rt.arrays(sample);valid=a['valid'];x=cal.apply_calibration(a['raw_wb'],calibration)
        accepted=row['decision']=='04' and row['iso']=='200' and row['ambiguous']=='False' and row['poor_fit']=='False'
        prediction=m.predict('04',x)
        err=rt.cm.delta_e00(rt.lab(prediction[valid]),rt.lab(a['jpeg'][valid]))
        coverage={}
        for style,d in dense.items():
            std,styled,support,distance=d.labs(x[valid])
            coverage[style]=dict(total=int(valid.sum()),supported=int(support.sum()),
                                fraction=float(support.mean()) if support.size else None)
            targetcoverage[style].append(coverage[style])
        if accepted:
            errors.extend(err);base04.append(dict(id=name,error=rt.stats(err)))
        out.append(dict(id=name,iso=int(row['iso']),inferred_recipe=row['decision'],
                        ambiguous=row['ambiguous']=='True',poor_fit=row['poor_fit']=='True',
                        eligible04=accepted,coverage=coverage))
    rt.dump('bridge/daily.json',dict(n=len(rows),processed=len(out),frames=out,
                conservative_iso200_inferred04=base04,pooled04_residual=rt.stats(errors),
                recipe_labels_are_inferred=True,actual_new01_or02_measured=False,
                scope='04-model transfer and target coverage, not true GR IV similarity'))
    print('daily',len(out),'inferred04 ISO200',len(base04),'pooled',rt.stats(errors),flush=True)


def main():
    (rt.LOCAL/'bridge').mkdir(exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['matrices','native','daily','all']);a=ap.parse_args()
    for name,fn in [('matrices',matrices),('native',native),('daily',daily)]:
        if a.action in (name,'all'):fn()


if __name__=='__main__':main()
