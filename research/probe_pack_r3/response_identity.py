"""Classify a RAW-corrected response without using photo order or the screen label."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key]='1'
import numpy as np

KEYS=('RP','RN','GP','GN','BP','BN')


def fit_response(observed,basis,inputs):
    residual=[];centered=[]
    for c in range(3):
        nuisance=np.c_[np.ones(len(inputs)),inputs[:,c]/1000]
        v=observed[:,c];b=basis[:,c]
        residual.append(v-nuisance@np.linalg.lstsq(nuisance,v,rcond=None)[0])
        centered.append(b-nuisance@np.linalg.lstsq(nuisance,b,rcond=None)[0])
    v=np.array(residual).T;b=np.array(centered).T
    norm=float(np.sum(b*b));amplitude=float(np.sum(v*b)/norm) if norm>1e-6 else 0
    prediction=np.clip(amplitude,0,3)*b
    return dict(amplitude=amplitude,improvement=float(np.sum(v*v)-np.sum((v-prediction)**2)),
        rmse=float(np.sqrt(np.mean((v-prediction)**2))),null_rmse=float(np.sqrt(np.mean(v*v))),
        active_points=int(np.sum(np.sum(b*b,axis=1)>.05)))


def identify(observed,inputs,templates):
    """Inputs are gray-patch RGB differences after RAW drift correction, not JPG alone."""
    observed=np.asarray(observed,float);inputs=np.asarray(inputs,float)
    assert observed.shape==inputs.shape and observed.ndim==2 and observed.shape[1]==3
    assert np.isfinite(observed).all() and np.isfinite(inputs).all()
    assert len(observed)>=12 and set(templates)==set(KEYS)
    fits={key:fit_response(observed,np.asarray(templates[key],float),inputs) for key in KEYS}
    order=sorted(KEYS,key=lambda k:fits[k]['improvement'],reverse=True)
    best,second=order[:2];score=fits[best];gain=score['improvement']
    null=score['null_rmse'];margin=gain-fits[second]['improvement']
    if null<.35 and gain<2:
        entry='A'
    elif (gain>2 and margin>1 and .35<score['amplitude']<3 and
          score['active_points']>=3 and score['rmse']<.65):
        entry=best
    else:
        entry='unknown'
    return dict(response_identity=entry,best_template=best,second_template=second,
        margin=margin,fits=fits,photo_order_used=False,photo_label_used=False,
        scope='Identity within seven candidate recipes; A compatibility is not a DAT hash or a shot number.')


def attach_label(response,photo_label=None):
    """Retain the two observations. A stale or missing label never changes the response score."""
    result=dict(response)
    result['photo_label']=photo_label
    label_entry=photo_label.get('entry') if photo_label else None
    entry=result['response_identity']
    result['label_response_conflict']=label_entry is not None and entry!='unknown' and label_entry!=entry
    result['label_unavailable']=photo_label is None
    return result
