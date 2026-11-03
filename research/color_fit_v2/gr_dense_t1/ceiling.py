"""Continuous numerical envelopes and exact least-squares tangent projections.

These are within the measured support. No nonlinear solver supplies a proof
of a global optimum, and no projection proves that only a 3D LUT can fix it.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
from fit import Fit
from prepare_dense import path as dataset_path
from analyze_dense import decomposition
import argparse
import numpy as np


def project(J, residual):
    coef, _, rank, singular = np.linalg.lstsq(J, residual, rcond=1e-9)
    left = residual-J@coef
    return left, dict(rank=int(rank), parameters=J.shape[1], residual_squared=float(left@left),
                      removable_squared_fraction=float(1-left@left/(residual@residual)),
                      coefficient_norm=float(np.linalg.norm(coef)))


def basis(h, L, C=None):
    angle = (h % 360)/30
    k = np.floor(angle).astype(int)
    u = angle-k
    H = np.zeros((len(h),12))
    H[np.arange(len(h)),k] = 1-u
    H[np.arange(len(h)),(k+1)%12] = u
    A = r.weights(L, np.arange(0,101,20))
    if C is None:
        return np.einsum('nh,nl->nhl',H,A).reshape(len(h),-1)
    B = r.weights(C, np.array([0.,8.,25.,50.,100.]))
    return np.einsum('nh,nl,nc->nhlc',H,A,B).reshape(len(h),-1)


def tangent(group, slot):
    P=Fit(group,slot,'c',oracle=True)
    d=P.d; use=d['eval_valid']
    x,target=d['x'][use],d['eval_target'][use]
    baseline=P.baseline_theta()
    residual,J=P.lab_parts(baseline,x,target)
    R=residual.ravel(); J=J.reshape(-1,P.np)
    total=float(R@R)
    selections=dict(Y=list(range(2)),sector24=list(range(2,50)),
                    T1=list(range(P.ns,P.np)),T3=list(range(50,P.ns)),
                    a=list(range(50)),b=list(range(50))+list(range(P.ns,P.np)),c=list(range(P.np)))
    outputs={}; residuals={}
    for name,sel in selections.items():
        left,stats=project(J[:,sel],R)
        outputs[name]=stats;residuals[name]=left
    base=r.FS.lab_from_codes(d['rgb04'][use]);L,C,h=r.FS.lch(base)
    v=residuals['c'].reshape(-1,3)
    spatial=((d['source_xy'][use,0]//128)+2*(d['source_xy'][use,1]//128))%4
    extension={}
    for name,B in [('hue_L',basis(h,L)),('hue_L_C',basis(h,L,C))]:
        cf,_,rank,_=np.linalg.lstsq(B,v,rcond=1e-9)
        after=v-B@cf
        cv=np.zeros_like(v)
        for fold in range(4):
            train=spatial!=fold;test=~train
            coef=np.linalg.lstsq(B[train],v[train],rcond=1e-9)[0]
            cv[test]=v[test]-B[test]@coef
        extension[name]=dict(rank=int(rank),parameters_per_component=B.shape[1],
            explains_of_remaining_squared=float(1-np.sum(after**2)/np.sum(v**2)),
            explains_of_original_squared=float((np.sum(v**2)-np.sum(after**2))/total),
            same_source_spatial_cv_explains_of_remaining=float(1-np.sum(cv**2)/np.sum(v**2)),
            same_source_spatial_cv_not_independent_camera_or_scene=True)
    # Separate ordinary tonal residual from hue-dependent lightness in the
    # observed residual, rather than equating all delta-L with a 3D requirement.
    light=residual[:,0]
    globalB=np.column_stack([r.weights(L,np.arange(0,101,20)),r.weights(C,np.array([0.,8.,25.,50.,100.]))[:,1:]])
    gl=light-globalB@np.linalg.lstsq(globalB,light,rcond=1e-9)[0]
    HB=basis(h,L)
    combined=np.column_stack([globalB,HB])
    hl=light-combined@np.linalg.lstsq(combined,light,rcond=1e-9)[0]
    light_effect=dict(raw_L_energy_fraction=float(light@light/total),
          global_L_C_removable_fraction_of_original=float((light@light-gl@gl)/total),
          additional_hue_L_removable_fraction_of_original=float((gl@gl-hl@hl)/total))
    out=dict(group=group,slot=slot,n=int(use.sum()),baseline_squared=total,
             tangent_projection=outputs,residual_extension=extension,hue_lightness=light_effect,
             interpretation='exact optimum of the local unconstrained linear model only; not a global nonlinear bound',
             no_integer_no_safety_no_grey_restriction_in_projection=True,
             remaining_is_not_proof_of_exclusive_3D_requirement=True)
    r.dump(r.HERE/f'projection_{group}_{slot}.json',out)
    print(group,slot,'projection removable', {k:round(v['removable_squared_fraction'],4) for k,v in outputs.items()},flush=True)


def oracle(group,slot,name,max_nfev=160):
    level={'Y':'a','sector24':'a','T1':'b','T3':'c','a':'a','b':'b','c':'c'}[name]
    P=Fit(group,slot,level,oracle=True)
    d=P.d;use=d['eval_valid']
    P.x,P.target=d['x'][use],d['eval_target'][use]
    P.w=np.ones(use.sum())
    P.R=np.empty((0,P.np))
    P._key=None
    base=P.baseline_theta()
    selection={'Y':list(range(2)), 'sector24':list(range(2,50)),
               'T1':list(range(P.ns,P.np)), 'T3':list(range(50,P.ns)),
               'a':list(range(50)), 'b':list(range(P.np)), 'c':list(range(P.np))}[name]
    sel=np.array(selection)
    low=np.full(P.np,-np.inf);high=-low
    low[:2],high[:2]=-.5,.5
    low[2:26],high[2:26]=np.log(.15),np.log(3)
    low[26:50],high[26:50]=-.9,.9
    if P.free:low[50:P.ns],high[50:P.ns]=-60,60
    if P.t1:low[P.ns:],high[P.ns:]=-55,55
    def expand(v):
        out=base.copy();out[sel]=v;return out
    # The final continuous table must stay encodable, monotone, and in range.
    def fun(v):
        th=expand(v)
        return np.r_[P.data_parts(th)[0],P.extra_constraints(th)]
    def jac(v):
        th=expand(v)
        return np.vstack([P.data_parts(th)[1],P.extra_constraints(th,True)[1]])[:,sel]
    runs=[]
    for start in ('round5','stock') if name in ('a','b','c') else ('round5',):
        xx=base[sel].copy() if start=='round5' else np.zeros(len(sel))
        result=r.least_squares(fun,np.clip(xx,low[sel]+1e-8,high[sel]-1e-8),jac=jac,
            bounds=(low[sel],high[sel]),max_nfev=max_nfev,x_scale='jac',ftol=2e-4,xtol=1e-5,gtol=1e-3)
        th=expand(result.x)
        lab=r.FS.lab_from_codes(P.predict(th,P.x))
        sc=r.score(P.target,lab,r.FS.lab_from_codes(d['rgb04'][use]))
        runs.append(dict(start=start,theta=th,score=sc,success=bool(result.success),nfev=result.nfev,
                         squared_DE00=float(np.sum(r.FS.delta_e00(P.target,lab)**2)),
                         objective=float(2*result.cost),optimality=float(result.optimality),
                         max_encoding_constraint_penalty=float(abs(P.extra_constraints(th)).max(initial=0))))
    best=min(runs,key=lambda x:x['objective'])
    _,curve=P.parameters(np.asarray(best['theta']))
    out=dict(group=group,slot=slot,lever=name,level=level,selected_parameters=selection,runs=runs,best=best,
         curve_min_increment=float(np.diff(curve,axis=1).min()),min_curve_value=float(curve.min()),
         max_curve_value=float(curve.max()),min_curve_endpoint=float(curve[:,-1].min()),
         baseline=r.score(P.target,r.P.prediction(P.D,P.D.current,P.x),r.FS.lab_from_codes(d['rgb04'][use])),
         no_grey_no_safety_no_anchors=True,not_global_optimum_certificate=True,
         accepted=False,firmware_ready=False,deployable=False)
    r.dump(r.LOCAL/f'oracle/{group}_{slot}_{name}.json',out)
    print(group,slot,'oracle',name,'similarity',round(best['score']['similarity'],5),
          'median',round(best['score']['median'],5),'nfev',best['nfev'],'converged',best['success'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=('project','oracle'))
    p.add_argument('--group',required=True,choices=('gr3','gr4_hdf'))
    p.add_argument('--slot',required=True,choices=('01','02'))
    p.add_argument('--lever',choices=('Y','sector24','T1','T3','a','b','c'))
    a=p.parse_args()
    tangent(a.group,a.slot) if a.command=='project' else oracle(a.group,a.slot,a.lever)
