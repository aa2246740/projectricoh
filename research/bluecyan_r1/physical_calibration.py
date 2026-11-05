#!/usr/bin/env python3
"""Refit only the prior October-24 native04 input map after fixing C040."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import history as h
import physical
import experiments as e
from analyze import ROOT,LOCAL,np,read,dump,de,stats,sha
from scipy.optimize import least_squares
import types


def apply(raw,C):
    u=np.asarray(raw)/4095;H=np.c_[np.ones(len(u)),u]
    if len(C)==10:
        r,g,b=u.T;H=np.c_[H,r*r,g*g,b*b,r*g,r*b,g*b]
    return raw+4095*(H@C)


def coefficients(unit):
    p=LOCAL/f'physical/input-map-{unit}.json'
    if p.exists():return np.array(read(p)['coefficients'])
    return np.array(read(ROOT/f'research/recipe_redo_r1/local/inputs/{unit}/definition.json')['calibration_coefficients'])


def main():
    unit='mount-a12';hm=h.Models();raw13=read(LOCAL/'history/inventory.json')[0]['metadata']['color_raw13']
    model=physical.update_model(hm.model(unit,200,raw13),unit)
    stock=(LOCAL/next(r['record'] for r in hm.bank if r['unit']==2 and '04' in r['labels'])).read_bytes()
    previous=read(ROOT/'research/recipe_redo_r1/local/calibration/mount-a12/mount_screen_20261101_degree1.json')
    source=ROOT/'research/recipe_redo_r1/local/calibration/mount-a12/dataset.npz'
    with np.load(source,allow_pickle=False) as z:data=dict(z)
    train=np.isin(data['group'],previous['training_groups'])
    raw=data['raw']*4095;observed=data['observed'];C0=np.array(previous['coefficients']);shape=C0.shape
    weights=np.zeros(len(raw))
    for frame in np.unique(data['frame'][train]):
        ix=(data['frame']==frame)&train;weights[ix]=1/(ix.sum()*len(np.unique(data['frame'][train])))
    weights[train]/=weights[train].mean();w=np.sqrt(weights[train]/(1+data['jpeg_sd'][train].mean(1)**2))
    def residual(flat):
        C=flat.reshape(shape);pred=model.predict(stock,apply(raw[train],C))
        return np.r_[((pred-observed[train])*w[:,None]).ravel(),(C[1:]*.1).ravel(),(C[:1]*2).ravel()]
    guard=e.load_solver();reference=types.SimpleNamespace(row=model.mm.MatrixRow.from_bytes(stock[216:244]))
    P=e.LeastProblem(residual,C0.ravel(),[-.25]*C0.size,[.25]*C0.size,'physical_input_map',raw[train],observed[train],reference)
    start,receipt=guard.solve(P,C0.ravel(),80)
    exact=least_squares(residual,start,bounds=(P.lower,P.upper),jac='3-point',max_nfev=100,
                        x_scale='jac',ftol=2e-7,xtol=2e-7,gtol=1e-5)
    C=exact.x.reshape(shape);scores={}
    oldmodel=h.Models().model(unit,200,raw13)
    old=oldmodel.predict(stock,apply(raw,C0));fixed_nodes_old_map=model.predict(stock,apply(raw,C0));new=model.predict(stock,apply(raw,C))
    for group in sorted(set(data['group'])):
        ix=data['group']==group
        scores[group]=dict(n=int(ix.sum()),training=bool(np.any(train[ix])),old=stats(de(old[ix],observed[ix])),
            fixed_nodes_old_map=stats(de(fixed_nodes_old_map[ix],observed[ix])),physical=stats(de(new[ix],observed[ix])))
        print(group,'train' if scores[group]['training'] else 'held',scores[group],flush=True)
    dump(f'physical/input-map-{unit}.json',dict(unit=unit,coefficients=C,previous_coefficients=C0,
        training_groups=previous['training_groups'],training_points=int(train.sum()),
        solver='fit_fast guarded_normal, then reference exact SciPy SVD',guarded=receipt,
        exact=dict(success=bool(exact.success),nfev=int(exact.nfev),cost=float(exact.cost),message=exact.message),
        source_sha256=sha(source),scores=scores,model_nodes_sha256=sha(LOCAL/f'physical/ring-{unit}-200.json'),
        all_new_noon_pages_and_historical_private_photos_excluded=True,
        no_per_photo_exposure_or_wb_fit=True))


if __name__=='__main__':main()
