"""PCA sensitivity estimates conditional on public chart averages and weak DNG constraints.

The ensemble is a model/assumption sensitivity analysis, not a calibrated confidence interval.
Camera gains and illuminant spectrum are not independently observed.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from prepare_data import daylight
from scipy.optimize import least_squares
from scipy.ndimage import gaussian_filter1d
from raw_io import tags
import argparse


DATA=None


def data():
    global DATA
    if DATA is None: DATA=c.arrays(c.LOCAL/'public_data.npz')
    return DATA


def spd(name):
    a=data();e=a[name]
    return e/(e@a['observer'][:,1])


def source_matrix(camera, temperature=6504.):
    d=c.read(c.LOCAL/f'matrix_{camera}.json')
    return c.cm.camera_matrix_at_temperature({int(k):v for k,v in d.items()},temperature)[0]


def prepare_metadata():
    for name,path in [('gxr','artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG'),
                      ('griv','artifacts/downloads/dpreview-gr4-studio/gr4_studio_daylight_iso100.dng')]:
        override=c.LOCAL/f'chart_override_{name}.json'
        if override.exists():path=c.read(override)['matrix_source']
        t=tags(path)
        keys=(50721,50722,50723,50724,50727,50728,50730,50778,50779,50931,50932,50964,50965)
        c.dump(f'matrix_{name}.json',{k:t[k] for k in keys if k in t})


def matrix_operator(e):
    a=data(); e=e/(e@a['observer'][:,1]);r=a['cc']
    xyz=r@(e[:,None]*a['observer']);white=e@a['observer']
    # Include a white observation to prevent an arbitrary neutral-axis fit.
    design=np.r_[xyz,white[None]*3]
    f=np.linalg.pinv(design)
    return f,white


def predicted_matrix(s,e):
    a=data();e=e/(e@a['observer'][:,1]);f,white=matrix_operator(e)
    rgb=a['cc']@(s.T*e[:,None]);rgb/=s@e
    m=(f@np.r_[rgb,np.ones((1,3))*3]).T
    return m/(m@white)[:,None]


def normalize_sensitivity(s):
    s=np.maximum(s,1e-12)
    return s/(s@spd('D65'))[...,None]


def make_prior(exclude=None,pcs=4,sibling_weight=0.):
    a=data();s=a['camera_sensitivities']
    s=gaussian_filter1d(s,.55,axis=-1,mode='nearest')
    s=normalize_sensitivity(s)
    names=a['camera_names'];use=np.ones(len(s),bool)
    if exclude is not None:use[exclude]=False
    s=s[use];mean=s.mean(axis=0)
    if sibling_weight:
        sibling=np.mean([normalize_sensitivity(gaussian_filter1d(a['camera_sensitivities'][i],.55,axis=-1))
                         for i,n in enumerate(names) if n in ('Nikon D90','Nikon D300s')],axis=0)
        mean=(1-sibling_weight)*mean+sibling_weight*sibling
    bases=[];fractions=[]
    for k in range(3):
        _,singular,v=np.linalg.svd(s[:,k]-s[:,k].mean(axis=0),full_matrices=False)
        bases.append(v[:pcs]* (singular[:pcs]/np.sqrt(len(s)-1))[:,None])
        fractions.append(float(np.sum(singular[:pcs]**2)/np.sum(singular**2)))
    return mean,np.array(bases),fractions


def chart(camera='gxr',modern=True):
    path=c.LOCAL/('patches_griv.json' if camera=='griv' else 'patches.json')
    override=c.LOCAL/f'chart_override_{camera}.json'
    cc_key='cc_modern' if camera=='griv' and modern else 'cc'
    if override.exists():
        info=c.read(override);path=info['patch_file'];cc_key=info['reference']
    rows=c.read(path)
    rows=[r for r in rows if r['chart']=='ColorChecker' and r['usable']]
    xy=np.array([r['nominal_preview_xy'] for r in rows])
    xy=(xy-xy.mean(axis=0))/np.maximum(np.ptp(xy,axis=0),1)
    return dict(index=np.array([r['index'] for r in rows]),
        observed=np.array([r['raw_trimmed'] for r in rows]),
        xy=xy,cc_key=cc_key,
        sigma=np.array([max(.025 if r['status']=='primary' else .04,
                            max(r['quadrant_relative_range'])/2) for r in rows]),rows=rows)


def fit(camera='gxr',pcs=4,matrix_sigma=.08,prior_scale=1.,chart_noise=1.,
        sibling_weight=0.,exclude_prior=None,chart_data=None,held_indices=(),
        pure_daylight=False,matrices=None,max_nfev=350,modern=True,veiling=True):
    a=data();mean,basis,fraction=make_prior(exclude_prior,pcs,sibling_weight)
    if matrices is None:
        matrices=[source_matrix(camera,2856),source_matrix(camera,6504)]
    e_matrices=[spd('A'),spd('D65')]
    targets=[]
    for m,e in zip(matrices,e_matrices):
        white=e@a['observer'];targets.append(m/(m@white)[:,None])
    ch=chart(camera,modern) if chart_data is None and camera in ('gxr','griv') else chart_data
    chart_enabled=ch is not None
    n=3*pcs
    # Spectral shape is independent of stored channel gains; D65 matrix supplies their convention.
    gain=matrices[-1]@(spd('D65')@a['observer']);gain/=gain[1]
    use=None
    if chart_enabled:use=~np.isin(ch['index'],np.array(held_indices))
    p0=np.zeros(n+(9 if chart_enabled else 0))
    if chart_enabled:
        p0[n]=np.log(.18);p0[n+1]=np.log(4500/5000)
        p0[n+8]=.001
    lower=np.full(len(p0),-5.);upper=-lower
    if chart_enabled:
        lower[n:]=[-8,np.log(3500/5000),-.8,-.5,-.5,-.3,-.3,-2,0]
        upper[n:]=[2,np.log(9000/5000),1.4,.5,.5,.3,.3,2,.05]
    def unpack(p):
        raw=mean+np.einsum('kp,kpw->kw',p[:n].reshape(3,pcs),basis)
        s=normalize_sensitivity(raw)
        return s,raw
    def illuminate(p):
        t=5000*np.exp(p[n+1]);e=daylight(t,a)
        green=0. if pure_daylight else p[n+2]
        e=e*np.exp(green*np.exp(-.5*((a['wave']-540)/45)**2))
        return e/(e@a['observer'][:,1])
    def predict(p):
        s,_=unpack(p);e=illuminate(p)
        g=gain*np.exp([p[n+3],0,p[n+4]])
        rgb=a[ch.get('cc_key','cc')][ch['index']]@((s*g[:,None]).T*e[:,None])
        veil=p[n+8] if veiling else 0
        rgb=rgb+veil*((s*g[:,None])@e)[None]
        shade=np.exp(p[n]+ch['xy']@p[n+5:n+7])
        return np.maximum(rgb*shade[:,None]+p[n+7]/4095,1e-8)
    def residual(p):
        s,raw=unpack(p)
        blocks=[p[:n]/prior_scale]
        for target,e in zip(targets,e_matrices):
            blocks.append(((predicted_matrix(s,e)-target)/matrix_sigma).ravel())
        blocks.append((np.minimum(raw,0)/(np.maximum(mean.max(axis=1),1e-8)[:,None]*.01)).ravel())
        if chart_enabled:
            pred=predict(p)
            blocks.append((np.log(pred[use]/ch['observed'][use])/(ch['sigma'][use,None]*chart_noise)).ravel())
            blocks.append(np.array([p[n+1]/.28,p[n+2]/(.001 if pure_daylight else .5),
                           p[n+3]/.08,p[n+4]/.08,p[n+5]/.035,p[n+6]/.035,p[n+7]/1,
                           p[n+8]/(.01 if veiling else .00001)]))
        return np.concatenate(blocks)
    result=least_squares(residual,p0,bounds=(lower,upper),max_nfev=max_nfev,ftol=1e-9,xtol=1e-9,gtol=1e-7)
    s,_=unpack(result.x)
    cov=np.linalg.pinv(result.jac.T@result.jac)
    info=dict(camera=camera,pcs_per_channel=pcs,prior_explained_variance=fraction,
          matrix_sigma=matrix_sigma,prior_scale=prior_scale,chart_noise=chart_noise,
          sibling_weight=sibling_weight,prior_camera_excluded=exclude_prior,success=bool(result.success),
          nfev=result.nfev,cost=float(result.cost),chart_conditioned=chart_enabled,
          empirical_confidence_interval=False,matrix_residuals=[c.stats(abs(predicted_matrix(s,e)-t).ravel())
                    for t,e in zip(targets,e_matrices)])
    if chart_enabled:
        pred=predict(result.x);error=np.abs(np.log(pred/ch['observed']))
        e=illuminate(result.x);xyz=e@a['observer'];xy=xyz[:2]/sum(xyz)
        info.update(illuminant_model='D-series times exp(green Gaussian), conditional on camera-gain convention',
                    nominal_daylight_K=float(5000*np.exp(result.x[n+1])),illuminant_xy=xy,
                    green_log_amplitude=float(result.x[n+2]),per_channel_gain_log=[float(result.x[n+3]),float(result.x[n+4])],
                    exposure=float(np.exp(result.x[n])),local_shading_log_slopes=result.x[n+5:n+7],
                    residual_black_DN=float(result.x[n+7]),chart_log_relative_error=c.stats(error.ravel()),
                    neutral_veiling_reflectance=float(result.x[n+8]) if veiling else 0,
                    chart_reference=ch.get('cc_key','cc'),
                    training_patch_count=int(use.sum()),held_patch_ids=(ch['index'][~use]+1).tolist(),
                    spectral_truth_measured=False)
    return dict(s=s,parameter=result.x,cov=cov,mean=mean,basis=basis,bounds=(lower,upper),
                info=info,predict=predict if chart_enabled else None,
                predicted_chart=predict(result.x) if chart_enabled else None)


def draw(fit_result,count,rng):
    p=rng.multivariate_normal(fit_result['parameter'],fit_result['cov'],size=count)
    p=np.clip(p,*fit_result['bounds'])
    n=fit_result['basis'].shape[1]
    s=fit_result['mean'][None]+np.einsum('dkp,kpw->dkw',p[:,:3*n].reshape(count,3,n),fit_result['basis'])
    return normalize_sensitivity(s)


def chart_cross_validation(camera='gxr'):
    ch=chart(camera);groups=[[2,7,12],[0,1,8,14,16],[3,5,10,13,17],[6,11,15],[4,9]]
    result=[];errors=[]
    # Fixed source-space display transform only changes units; it adds no target-camera evidence.
    extraction=c.read(c.LOCAL/('extraction_griv.json' if camera=='griv' else 'extraction.json'))
    white_info=extraction['matrix_conditioned_white'];xy=white_info['white_xy']
    white=np.array([xy[0]/xy[1],1,(1-sum(xy))/xy[1]])
    m=source_matrix(camera,white_info['cct_K'])
    adapt=c.cm.cat(white,c.cm.D65);inverse=adapt@np.linalg.inv(m)
    for group in groups:
        held=[v for v in group if v in ch['index']]
        f=fit(camera,held_indices=held)
        use=np.isin(ch['index'],held)
        pred=f['predicted_chart'][use];obs=ch['observed'][use]
        # Match only global radiometric scale from the training neutral; no held-out exposure fit.
        expo=f['info']['exposure'];predlab=c.cm.xyz_lab((pred/expo)@inverse.T,c.cm.D65)
        obslab=c.cm.xyz_lab((obs/expo)@inverse.T,c.cm.D65)
        de=c.cm.delta_e00(predlab,obslab);errors.extend(de)
        result.append(dict(held_ids=(ch['index'][use]+1).tolist(),raw_relative_error=c.stats(abs(pred/obs-1).ravel()),
                           GXR_matrix_Lab_residual=c.stats(de),fit_success=f['info']['success']))
    c.dump(f'chart_holdout_{camera}.json',dict(folds=result,pooled_camera_matrix_Lab_residual=c.stats(errors),
          units='predicted and observed native camera RAW through one fixed display transform; not cross-camera accuracy',
          display_white_source='all usable neutral patches only, frozen before colored-family holdout',
          display_white_xy=xy,display_matrix_temperature_K=white_info['cct_K'],
          independent_colored_patches=len(errors),groups='color families; neutrals retained only for exposure/illumination',
          chart_spectra_are_average=True))
    print(camera,'color-family holdout',c.stats(errors))


def simulated_matrix_validation():
    a=data();results=[];all_errors=[]
    for i,name in enumerate(a['camera_names']):
        s=normalize_sensitivity(gaussian_filter1d(a['camera_sensitivities'][i],.55,axis=-1))
        ms=[predicted_matrix(s,spd(k)) for k in ('A','D65')]
        f=fit('simulated-matrix-only',exclude_prior=i,matrices=ms,pcs=4)
        e=spd('D65');r=a['natural'];obs=r@(s.T*e[:,None]);pred=r@(f['s'].T*e[:,None])
        white=e@a['observer'];inv=np.linalg.inv(ms[-1]);adapt=c.cm.cat(white,c.cm.D65)
        de=c.cm.delta_e00(c.cm.xyz_lab(pred@inv.T@adapt.T,c.cm.D65),
                          c.cm.xyz_lab(obs@inv.T@adapt.T,c.cm.D65))
        all_errors.extend(de);results.append(dict(camera=name,natural_error=c.stats(de),success=f['info']['success']))
    c.dump('prior_validation.json',dict(results=results,pooled_error=c.stats(all_errors),
        scope='leave-one-camera-out, ideal synthetic matrices derived using this model, not vendor matrices',
        proves_target_camera_accuracy=False))
    print('matrix-only prior held-camera validation',c.stats(all_errors))


def main():
    prepare_metadata();rng=np.random.default_rng(20261026)
    configurations=[dict(pcs=4),dict(pcs=2),dict(pcs=6),dict(pcs=4,matrix_sigma=.04),
                    dict(pcs=4,matrix_sigma=.12),dict(pcs=4,chart_noise=1.6),
                    dict(pcs=4,sibling_weight=.2),dict(pcs=4,prior_scale=1.8),
                    dict(pcs=4,modern=False),dict(pcs=4,veiling=False)]
    sg=[];st=[];records=[];centres=[]
    for i,config in enumerate(configurations):
        source=fit('gxr',**config)
        target_config={k:v for k,v in config.items() if k not in ('sibling_weight',)}
        target=fit('griv',**target_config)
        sg.extend(draw(source,8,rng));st.extend(draw(target,8,rng))
        centres.append(np.stack([source['s'],target['s']]))
        records.append(dict(configuration=i,source=source['info'],target=target['info']))
        print('fit',i,'costs',round(source['info']['cost'],2),round(target['info']['cost'],2),
              'K',round(source['info']['nominal_daylight_K']),'success',source['info']['success'],target['info']['success'],flush=True)
    sg=np.array(sg);st=np.array(st);centres=np.array(centres)
    np.savez_compressed(c.LOCAL/'sensitivities.npz',gxr=sg,griv=st,centres=centres,wave=data()['wave'])
    pure=fit('gxr',pure_daylight=True)
    c.dump('sensitivity_fit.json',dict(configurations=records,ensemble_count=len(sg),
            pure_daylight_diagnostic=pure['info'],joint_radiometric_spectrum_identifiable=False,
            target='GR IV real public studio chart plus matrix and PCA prior; chart reference is generic, not measured individually',
            uncertainty='conditional local Gaussian draws plus explicit model variants; not calibrated credible intervals',
            normalization='each channel integrates to one under D65; channel gain is carried separately',
            full_sensitivity_and_private_metadata_location='local/ only'))
    chart_cross_validation('gxr');chart_cross_validation('griv');simulated_matrix_validation()
    print('frozen protected inputs',c.verify())


if __name__=='__main__': main()
