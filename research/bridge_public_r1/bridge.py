"""Natural-reflectance bridge simulations, conditional on estimated sensitivities.

Oracle fits know the simulated target responses; their residual is an empirical
limited-model error, not a proved metamerism floor for the real cameras.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from estimate import data,spd,source_matrix
from scipy.linalg import null_space


def features(x,kind):
    x=np.maximum(np.asarray(x),1e-12);r,g,b=x.T
    f=[r-g,b-g]
    if kind=='smooth': f.extend([np.sqrt(r*g)-g,np.sqrt(r*b)-g,np.sqrt(g*b)-g])
    return np.array(f).T


def fit_bridge(x,y,kind='linear'):
    q=features(x,kind);z=y-x[:,1,None]
    ridge=1e-5 if kind=='linear' else 1e-4
    penalty=ridge*np.trace(q.T@q)/q.shape[1]
    coef=np.linalg.solve(q.T@q+penalty*np.eye(q.shape[1]),q.T@z)
    return dict(kind=kind,coef=coef)


def apply(model,x):
    if 'matrix' in model: return np.asarray(x)@np.asarray(model['matrix']).T
    return np.asarray(x)[:,1,None]+features(x,model['kind'])@np.asarray(model['coef'])


def matrix_model(temperature):
    a=data();e=spd('D65') if temperature==6504 else None
    if e is None:
        from prepare_data import daylight
        e=daylight(temperature,a);e=e/(e@a['observer'][:,1])
    white=e@a['observer'];mg=source_matrix('gxr',temperature);mt=source_matrix('griv',temperature)
    ng=mg@white;nt=mt@white
    return dict(matrix=np.diag(1/nt)@mt@np.linalg.inv(mg)@np.diag(ng))


def response(s,r,e):
    s=s/(s@e)[:,None]
    return r@(s.T*e[:,None])


def lab_from_target(y,temperature,e):
    white=e@data()['observer'];m=source_matrix('griv',temperature)
    transform=c.cm.cat(white,c.cm.D65)@np.linalg.inv(m)@np.diag(m@white)
    return c.cm.xyz_lab(np.asarray(y)@transform.T,c.cm.D65)


def summary_over_models(errors):
    a=np.asarray(errors)
    med=np.median(a,axis=1);p90=np.percentile(a,90,axis=1)
    return dict(pooled=c.stats(a.ravel()),per_model_median_p05_p50_p95=np.percentile(med,[5,50,95]),
                per_model_p90_p05_p50_p95=np.percentile(p90,[5,50,95]),
                calibrated_interval=False)


def metamers(sg,st,train,test,e):
    mean=train.mean(axis=0);_,sigma,v=np.linalg.svd(train-mean,full_matrices=False)
    basis=v[:6]*(sigma[:6]/np.sqrt(len(train)-1))[:,None]
    k=null_space((sg*e)@basis.T)
    rng=np.random.default_rng(20261026);a=[];b=[];deltas=[];residual=[]
    for reflectance in test[:120]:
        direction=(rng.normal(size=k.shape[1])@k.T)@basis
        direction/=max(np.max(abs(direction)),1e-12)
        positive=direction>0;negative=direction<0
        high=min(np.min((1-reflectance[positive])/direction[positive]) if positive.any() else 1,
                 np.min(-reflectance[negative]/direction[negative]) if negative.any() else 1,.05)
        if high<=1e-5: continue
        other=reflectance+direction*high*.95
        x1=response(sg,reflectance[None],e)[0];x2=response(sg,other[None],e)[0]
        y1=response(st,reflectance[None],e)[0];y2=response(st,other[None],e)[0]
        a.append(reflectance);b.append(other);residual.append(np.max(abs(x1-x2)))
        deltas.append(c.cm.delta_e00(lab_from_target(y1[None],6504,e),lab_from_target(y2[None],6504,e))[0])
    np.savez_compressed(c.LOCAL/'metamer_counterexamples.npz',reflectance_a=a,reflectance_b=b,
                        same_gxr_max_abs_difference=residual,target_DE00=deltas)
    return dict(n=len(deltas),same_gxr_max_abs_difference=float(max(residual)),target_separation=c.stats(deltas),
                construction='six-PC natural-reflectance nullspace, max 0.0475 reflectance perturbation, bounded [0,1]',
                estimated_camera_model=True,measured_real_camera=False,frequency_of_metamers_unknown=True,
                separation_is_not_a_median_error_floor=True)


def main():
    a=data();s=c.arrays(c.LOCAL/'sensitivities.npz');sg=s['gxr'];st=s['griv']
    rng=np.random.default_rng(714);order=rng.permutation(len(a['munsell']))
    train=a['munsell'][order[:len(order)//2]];test=a['munsell'][order[len(order)//2:]]
    np.savez_compressed(c.LOCAL/'reflectance_split.npz',train_indices=order[:len(order)//2],test_indices=order[len(order)//2:])
    e=spd('D65');point_g=s['centres'][0,0];point_t=s['centres'][0,1]
    point={kind:fit_bridge(response(point_g,train,e),response(point_t,train,e),kind) for kind in ('linear','smooth')}
    c.dump('bridge_models.json',dict(white_balanced_neutral_normalized=True,illuminant='D65',
           current_ColorMatrix=matrix_model(6504),PCA_point_linear=point['linear'],PCA_point_smooth=point['smooth'],
           recommended='current_ColorMatrix',reason='Both cameras chart-constrained; GXR spectral holdout still fails precision required for replacement',
           apply_to_existing_target_files=False))
    all_results=[];oracle_models=[];raw_errors=[]
    for name,temperature in [('D50',5003),('D55',5503),('D65',6504),('D75',7504)]:
        e=spd(name);base=matrix_model(temperature)
        xx=np.array([response(g,train,e) for g in sg]);yy=np.array([response(t,train,e) for t in st])
        shared={kind:fit_bridge(xx.reshape(-1,3),yy.reshape(-1,3),kind) for kind in ('linear','smooth')}
        for dataset,reflectances in [('Munsell_heldout',test),('natural_heldout',a['natural'])]:
            error={k:[] for k in ('ColorMatrix','shared_linear','shared_smooth','oracle_linear','oracle_smooth')}
            for i,(g,t) in enumerate(zip(sg,st)):
                x=response(g,reflectances,e);y=response(t,reflectances,e)
                candidates=dict(ColorMatrix=base,shared_linear=shared['linear'],shared_smooth=shared['smooth'])
                for kind in ('linear','smooth'):
                    model=fit_bridge(xx[i],yy[i],kind);candidates['oracle_'+kind]=model
                    if name=='D65' and dataset=='natural_heldout' and kind=='smooth': oracle_models.append(model['coef'])
                truth=lab_from_target(y,temperature,e)
                for key,model in candidates.items():
                    pred=apply(model,x);de=c.cm.delta_e00(lab_from_target(pred,temperature,e),truth)
                    error[key].append(de)
            for key,errors in error.items():
                all_results.append(dict(illuminant=name,temperature_K=temperature,dataset=dataset,method=key,
                          **summary_over_models(errors)))
                if name=='D65' and dataset=='natural_heldout':
                    raw_errors.append((key,np.array(errors)))
            print(name,dataset,'CM',round(all_results[-5]['pooled']['median'],3),
                  'oracle smooth',round(all_results[-1]['pooled']['median'],3),flush=True)
    # Explicitly remove the extrapolated natural tail instead of treating it as measured reflectance.
    e=spd('D65').copy();e[a['wave']>700]=0
    trunc=[]
    for g,t in zip(sg,st):
        x=response(g,a['natural'],e);y=response(t,a['natural'],e)
        trunc.extend(c.cm.delta_e00(lab_from_target(apply(matrix_model(6504),x),6504,e),lab_from_target(y,6504,e)))
    c.dump('bridge_simulation.json',dict(results=all_results,natural_400_700_only_CM=c.stats(trunc),
        natural_spectral_extent='400-700 nm measured, constant tail to 720 in main table',
        target_space='white-balanced GR IV camera RGB via frozen GR IV DNG inverse matrix, Bradford to D65 Lab',
        models=len(sg),training='634 Munsell; seed 714; all 219 natural and other 635 Munsell held out',
        target_camera_has_chart_measurement=True,source_chart_holdout_failed=True,
        empirical_oracle_mapping_residual_is_not_a_proven_metamerism_floor=True,
        actual_sensor_error_identifiable=False,
        conditional_metamer_examples=metamers(point_g,point_t,train,test,spd('D65'))))
    np.savez_compressed(c.LOCAL/'bridge_oracles.npz',smooth_coef=oracle_models,
                        **{key:errors for key,errors in raw_errors})
    # Behavior checks for both bridge kinds.
    probes=np.array([[.1,.2,.3],[.5,.4,.2],[.7,.7,.7]])
    checks=[]
    for kind,model in point.items():
        checks.append(dict(kind=kind,neutral_error=float(np.max(abs(apply(model,np.ones((1,3)))-1))),
                           exposure_homogeneity_error=float(np.max(abs(apply(model,probes*2)-apply(model,probes)*2)))))
    assert all(r['neutral_error']<1e-12 and r['exposure_homogeneity_error']<1e-12 for r in checks)
    c.dump('bridge_behavior_checks.json',checks)
    print('bridge simulations complete; actual camera error remains unidentified')


if __name__=='__main__': main()
