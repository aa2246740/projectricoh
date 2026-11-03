"""Propagate modeled bridge changes as Lab vectors through the frozen style pipeline.

This measures sensitivity of an existing empirical ceiling to a bridge assumption.
It is not a same-object cross-camera acceptance measurement or a physical floor.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from bridge import apply,response,fit_bridge
from estimate import data,spd
from scipy.spatial import Delaunay


def frozen_style():
    # Redirect only the I/O adapter; execute the frozen style math unchanged.
    # Importing the old runtime directly would write its input log outside this task.
    sys.modules['runtime']=c
    original=list(sys.path)
    try:return c.module('bridge_frozen_style','research/gr4_lut_ceiling/style.py')
    finally:sys.path[:]=original


def score(pred,target,baseline):
    error=c.cm.delta_e00(pred,target);den=c.cm.delta_e00(baseline,target)
    return dict(error=c.stats(error),baseline=c.stats(den),
                similarity_median=float(1-np.median(error)/np.median(den)))


def target_with_bridge(d,style_module,x,baseline,model):
    raw=apply(model,x/320)*d.anchor
    measured,valid,distance=d.raw_function(style_module.feature(raw))
    valid&=(raw>0).all(axis=1)
    target=style_module.relative(baseline,measured[:,:3],measured[:,3:])
    return target,valid


def natural_color_support(x):
    ss=c.arrays(c.LOCAL/'sensitivities.npz')['centres'][0,0]
    r=np.r_[data()['munsell'],data()['natural']]
    values=response(ss,r,spd('D65'))
    hull=Delaunay(values[:,[0,2]]/values[:,1,None])
    ratio=x[:,[0,2]]/np.maximum(x[:,1,None],1e-8)
    return (hull.find_simplex(ratio)>=0)&(x>0).all(axis=1)


def main():
    style=frozen_style();body=c.arrays('research/gr4_lut_ceiling/local/lut/body_data.npz')
    models=c.read(c.LOCAL/'bridge_models.json');oracle=c.arrays(c.LOCAL/'bridge_oracles.npz')['smooth_coef']
    x=body['x'];baseline=c.lab(body['base_rgb']);natural_support=natural_color_support(x)
    results=[]
    for k,(slot,name) in enumerate([('01','positive'),('02','negative')]):
        d=style.Dense(name);current,original_valid,_=d.target(x,baseline)
        valid=original_valid&body['supported'][:,k]
        assert np.max(abs(current[valid]-body['targets'][valid,k]))<1e-8, 'frozen target reproduction failed'
        scenarios=[];support=[]
        for coef in oracle:
            target,use=target_with_bridge(d,style,x,baseline,dict(kind='smooth',coef=coef))
            scenarios.append(target);support.append(use)
        scenarios=np.array(scenarios);support=np.array(support)
        all_model_support=support.all(axis=0)&valid
        point={}
        for method in ['PCA_point_linear','PCA_point_smooth']:
            target,use=target_with_bridge(d,style,x,baseline,models[method]);point[method]=(target,use)
        for scheme in ('patch','hue'):
            frozen=c.arrays(f'research/gr4_lut_ceiling/local/lut/body_{slot}_{scheme}_pixel33.npz')
            full_prediction=np.zeros_like(current)
            full_prediction[frozen['index']]=c.lab(frozen['prediction'])
            membership=np.zeros(len(x),bool);membership[frozen['index']]=True
            for subset in ('all_style_supported','within_natural_color_hull'):
                use=membership&all_model_support
                if subset=='within_natural_color_hull':use&=natural_support
                if not use.any():continue
                reference=score(full_prediction[use],current[use],baseline[use])
                gap=.95-reference['similarity_median']
                rows=[]
                for i,target in enumerate(scenarios):
                    shifted=score(full_prediction[use],target[use],baseline[use])
                    move=c.stats(c.cm.delta_e00(current[use],target[use]))
                    # Recompute numerator and denominator on identical samples; do not add median errors.
                    reduction=reference['similarity_median']-shifted['similarity_median']
                    rows.append(dict(model=i,target_shift=move,score=shifted,
                         score_change_percentage_points=-100*reduction,
                         conditional_gap_ratio=reduction/gap if gap>0 else None))
                scores=np.array([v['score']['similarity_median'] for v in rows]);shift=np.array([v['target_shift']['median'] for v in rows])
                ratios=[v['conditional_gap_ratio'] for v in rows if v['conditional_gap_ratio'] is not None]
                point_rows=[]
                for method,(target,supported) in point.items():
                    uu=use&supported
                    if uu.any():point_rows.append(dict(method=method,n=int(uu.sum()),
                        target_shift=c.stats(c.cm.delta_e00(current[uu],target[uu])),
                        score=score(full_prediction[uu],target[uu],baseline[uu])))
                results.append(dict(slot=slot,scheme=scheme,subset=subset,n=int(use.sum()),
                    original_frozen_population=len(frozen['index']),excluded=int(len(frozen['index'])-use.sum()),
                    original_full_score=float(1-np.median(frozen['error'])/np.median(frozen['baseline'])),
                    current_bridge_on_common_population=reference,
                    gap_to_95_percentage_points=100*gap,
                    conditional_score_p05_p50_p95=np.percentile(scores,[5,50,95]),
                    conditional_target_shift_median_p05_p50_p95=np.percentile(shift,[5,50,95]),
                    conditional_gap_ratio_p05_p50_p95=np.percentile(ratios,[5,50,95]) if ratios else None,
                    scenarios=rows,point_models=point_rows))
                print(slot,scheme,subset,'n',int(use.sum()),'current S',round(reference['similarity_median'],4),
                      'conditional S 5/50/95',np.round(np.percentile(scores,[5,50,95]),4).tolist(),flush=True)
        np.savez_compressed(c.LOCAL/f'propagation_{slot}.npz',current_target=current,
               modeled_targets=scenarios,model_support=support,natural_color_support=natural_support,
               original_support=valid,baseline=baseline)
    c.dump('ceiling_propagation.json',dict(results=results,
           metric='1 - median DE00(recipe,target) / median DE00(04,target), pooled first, identical population per comparison',
           propagated_by='change target Lab vectors, retain actual frozen 33-cube holdout prediction, recompute both deltas',
           input_convention='frozen calibrated GXR scene_x/320; equivalence to physical white-balanced response remains an assumption',
           uncertainty='model scenarios; generic chart reflectance, light spectrum and flare not independently measured',
           target_physical_truth=False,refitted_LUT=False,actual_unavoidable_share_of_gap_to_95=None,
           oracle_smooth_residual_in_natural_simulations_not_included_in_this_target_shift_projection=True,
           no_claim_of_physical_similarity_ceiling=True))
    native=c.arrays('research/gr4_lut_ceiling/local/bridge/R8051477.npz');use=native['valid']
    err=c.cm.delta_e00(c.lab(native['prediction'][use]),c.lab(native['observed'][use]))
    diagnostics=[]
    for name in ('positive','negative'):
        d=style.Dense(name);base=c.lab(native['observed']);current,valid,_=d.target(native['x'],base)
        target,support=target_with_bridge(d,style,native['x'],base,models['PCA_point_smooth'])
        uu=use&valid&support
        diagnostics.append(dict(style=name,n=int(uu.sum()),target_shift=c.stats(c.cm.delta_e00(current[uu],target[uu]))))
    daily=c.read('research/gr4_lut_ceiling/local/bridge/daily.json')
    calibration=c.read('research/refit_50mm_r7/local/folds/full/calibration.json')
    c.inp('research/module_adapt/calibrate.py')
    daylight=[]
    for record in daily['conservative_iso200_inferred04']:
        frame=c.arrays('research/daily_bugs_20261024/local/samples/'+record['id']+'.npz')
        # Exact frozen apply_calibration formula, without importing its unrelated runtime.
        r,g,b=frame['raw_wb'].T;columns=[np.ones(len(r)),r,g,b]
        if calibration['degree']==2:columns.extend([r*r,g*g,b*b,r*g,r*b,g*b])
        xx=4095*(frame['raw_wb']+np.column_stack(columns)@np.asarray(calibration['residual_coefficients']))
        base=c.lab(frame['jpeg']);per_style=[]
        for name in ('positive','negative'):
            d=style.Dense(name);current,valid,_=d.target(xx,base)
            target,support=target_with_bridge(d,style,xx,base,models['PCA_point_smooth'])
            uu=frame['valid']&valid&support
            per_style.append(dict(style=name,n=int(uu.sum()),
                target_shift=c.stats(c.cm.delta_e00(current[uu],target[uu]))))
        daylight.append(dict(id=record['id'],sample_count=int(frame['valid'].sum()),
                             frozen04_residual=record['error'],target_change=per_style))
    c.dump('gxr_existing_validation.json',dict(native_04_recomputed_error=c.stats(err),
        native_04_hash_verified=True,native_target_shift=diagnostics,
        daylight_04_existing_pooled_residual=daily['pooled04_residual'],
        daylight_frames=daily['conservative_iso200_inferred04'],
        daylight_point_model_diagnostics=daylight,
        daylight_evidence='frozen actual RAW/JPEG samples and existing renderer residual; recipe labels inferred',
        new_sensitivity_accuracy_validated_by_these_residuals=False,
        reason='a native GXR JPEG supplies renderer truth, not GR IV RAW or spectral ground truth'))
    print('native 04 residual independently remeasured from frozen samples',c.stats(err))


if __name__=='__main__': main()
