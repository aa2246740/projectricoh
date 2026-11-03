"""Fit the paired relative style change directly, retaining the frozen LCh rule."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from style import Dense,Function,relative,grouped,PAIRS
from isp import model
from scipy.interpolate import RBFInterpolator


def main():
    m=model();rows=[]
    for slot,style in [('01','positive'),('02','negative')]:
        d=Dense(style);a=d.a
        x=a['raw_wb']@np.linalg.inv(d.T).T*(320/d.anchor)
        base_rgb=m.predict('04',x);base=rt.lab(base_rgb)
        eligible=(x>0).all(1)&(x<4095).all(1)&(base_rgb>2).all(1)&(base_rgb<253).all(1)
        target=relative(base,a['standard'],a[style]);baseline=rt.cm.delta_e00(base,target)
        cs=np.linalg.norm(a['standard'][:,1:],axis=1);cp=np.linalg.norm(a[style][:,1:],axis=1)
        quotient=np.ones(len(x),complex);active=(cs>=8)&(cp>=8)
        np.divide(a[style][:,1]+1j*a[style][:,2],a['standard'][:,1]+1j*a['standard'][:,2],out=quotient,where=active)
        descriptor=np.c_[a[style][:,0]-a['standard'][:,0],quotient.real,quotient.imag]
        hue=(np.degrees(np.arctan2(a['standard'][:,2],a['standard'][:,1]))%360//15).astype(int)%3
        for scheme,groups in [('page',a['band']),('hue',hue)]:
            errors={method:[] for method in ('absolute_linear','relative_linear','relative_TPS64')};denom=[]
            for group in np.unique(groups):
                held=(groups==group)&eligible
                keys={tuple(q) for q in np.round(a['feature'][held],9)}
                train=np.array([not h and tuple(q) not in keys for h,q in zip(groups==group,np.round(a['feature'],9))])
                rawfunc=Function(a['feature'][train],np.c_[a['standard'][train],a[style][train]])
                pp,supported,_=rawfunc(a['feature'][held]);index=np.flatnonzero(held)[supported]
                actual=target[index];denom.extend(baseline[index]);pp=pp[supported]
                baseheld=base[index]
                predicted=relative(baseheld,pp[:,:3],pp[:,3:])
                errors['absolute_linear'].extend(rt.cm.delta_e00(predicted,actual))
                np.savez_compressed(rt.LOCAL/f'style/relative_{style}_{scheme}{group}_absolute_linear.npz',
                                    prediction_lab=predicted,target_lab=actual,baseline=baseline[index],index=index)
                xx,yy=grouped(a['feature'][train],descriptor[train])
                f1=Function(xx,yy)
                f2=RBFInterpolator(xx,yy,neighbors=64,smoothing=.001,kernel='thin_plate_spline',degree=1)
                for name,function in [('relative_linear',lambda q:f1(q)[0]),('relative_TPS64',f2)]:
                    delta=function(a['feature'][index])
                    active=(np.linalg.norm(pp[:,1:3],axis=1)>=8)&(np.linalg.norm(pp[:,4:6],axis=1)>=8)&(np.linalg.norm(baseheld[:,1:],axis=1)>=8)
                    q=np.where(active,delta[:,1]+1j*delta[:,2],1.)
                    ab=(baseheld[:,1]+1j*baseheld[:,2])*q
                    predicted=np.c_[baseheld[:,0]+delta[:,0],ab.real,ab.imag]
                    errors[name].extend(rt.cm.delta_e00(predicted,actual))
                    np.savez_compressed(rt.LOCAL/f'style/relative_{style}_{scheme}{group}_{name}.npz',
                                        prediction_lab=predicted,target_lab=actual,baseline=baseline[index],index=index)
            for method,error in errors.items():
                row=dict(slot=slot,scheme=scheme,method=method,**rt.score(error,denom),
                         exact_bridge_assumed=True,actual_GXR_same_scene_pixels=False,
                         target_LCh_rule_unchanged=True,no_extrapolation=True)
                rows.append(row);print('relative sampling',slot,scheme,method,row['similarity_median'],row['error']['median'],flush=True)
    rt.dump('style/relative_sampling.json',rows)


if __name__=='__main__':main()
