"""Fixed smooth interpolators on the same strict measured hull, no extrapolation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,Function,grouped,PAIRS
from scipy.interpolate import RBFInterpolator
import argparse

METHODS=[('thin_plate_64',64,.001),('thin_plate_128',128,.001)]


def cv():
    result=[]
    for style in PAIRS:
        a=Dense(style).a
        hue=(np.degrees(np.arctan2(a['standard'][:,2],a['standard'][:,1]))%360//15).astype(int)%3
        for domain in ('raw','standard'):
            x=a['feature'] if domain=='raw' else a['standard']/[20.,30.,30.]
            target=np.c_[a['standard'],a[style]] if domain=='raw' else a[style]
            for scheme,groups in [('page',a['band']),('hue',hue)]:
                collected={name:[] for name,_,_ in METHODS}
                standard={name:[] for name,_,_ in METHODS}
                count=0
                for group in np.unique(groups):
                    held=groups==group
                    keys={tuple(q) for q in np.round(a['feature'][held],9)}
                    train=np.array([not h and tuple(q) not in keys for h,q in zip(held,np.round(a['feature'],9))])
                    xx,yy=grouped(x[train],target[train]);hull=Function(xx,yy)
                    _,valid,_=hull(x[held]);query=x[held][valid];observed=target[held][valid];count+=len(query)
                    for name,neighbors,smoothing in METHODS:
                        f=RBFInterpolator(xx,yy,neighbors=neighbors,smoothing=smoothing,kernel='thin_plate_spline',degree=1)
                        pred=f(query)
                        collected[name].extend(rt.cm.delta_e00(pred[:,-3:],observed[:,-3:]))
                        if domain=='raw':standard[name].extend(rt.cm.delta_e00(pred[:,:3],observed[:,:3]))
                        np.savez_compressed(rt.LOCAL/f'smooth/{style}_{domain}_{scheme}{group}_{name}.npz',
                                            index=np.flatnonzero(held)[valid],prediction=pred,observed=observed)
                for name,neighbors,smoothing in METHODS:
                    row=dict(style=style,domain=domain,scheme=scheme,method=name,n=count,
                             style_error=rt.stats(collected[name]),standard_error=rt.stats(standard[name]),
                             hyperparameters_fixed_before_outer_results=True,no_extrapolation=True,
                             smoothing=smoothing,neighbors=neighbors)
                    result.append(row)
                    print(style,domain,scheme,name,round(row['style_error']['median'],4),flush=True)
    rt.dump('smooth/summary.json',result)


def main():
    (rt.LOCAL/'smooth').mkdir(exist_ok=True);cv()


if __name__=='__main__':main()
