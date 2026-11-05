#!/usr/bin/env python3
"""Choose model family by leave-one-T-page-out only, then freeze parameters."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import experiments as e
from analyze import np,ROOT,LOCAL,dump,de,stats,read
import time

FAMILIES={
    'old':dict(kind='old',start=[],lo=[],hi=[]),
    'ellipse3':dict(kind='ellipse',start=[0.,0.,0.],lo=[-40.,-.65,-.65],hi=[40.,.65,.65]),
    'delta_matrix4':dict(kind='delta_linear',start=[1.,0.,0.,0.],lo=[.2,-.8,-.8,-.8],hi=[1.8,.8,.8,.8]),
    'lookup6':dict(kind='nodes',start=[0.]*6,lo=[-55.]*6,hi=[55.]*6),
    'lookup12':dict(kind='nodes',start=[0.]*12,lo=[-40.]*12,hi=[40.]*12),
}


def main():
    _,ref,rows=a.load();d=e.Data(ref,rows);guard=e.load_solver();cm=a.colour_math()
    results={};pages=np.array([r['page'] for r in d.rows]);allT=d.train.copy()
    tlab=cm.rgb_lab(d.obs/255)
    for family,cfg in FAMILIES.items():
        folds=[]
        for page in ('T1','T2','T3','T4','all'):
            train=allT & (pages!=page);held=allT & (pages==page) if page!='all' else ~allT
            def residual(p):
                pred=d.predict(cfg['kind'],p)
                loss=ref.fs.de00_components(tlab[train],cm.rgb_lab(pred[train]/255)).ravel()/np.sqrt(train.sum())
                if cfg['kind']=='nodes':
                    # A monotone routing coordinate and weak curvature ridge.
                    diff=np.roll(p,-1)-p;step=360/len(p)
                    reg=np.r_[p*.001,(np.roll(p,1)-2*p+np.roll(p,-1))*.003,
                              np.minimum(1+diff/step-.2,0)*20]
                elif cfg['kind']=='delta_linear':reg=(p-np.array(cfg['start']))*.01
                else:reg=p*.001
                return np.r_[loss,reg]
            p=np.array(cfg['start']);receipt={}
            if len(p):
                P=e.LeastProblem(residual,p,cfg['lo'],cfg['hi'],family+'_'+page,d.x[train],d.obs[train],ref)
                p,receipt=guard.solve(P,p,100)
            pred=d.predict(cfg['kind'],p);errors=de(pred,d.obs)
            fold=dict(page=page,parameters=p,receipt=receipt,train=stats(errors[train]),held=stats(errors[held]),
                      held_mse=float(np.mean(errors[held]**2)))
            if page=='all':fold['scores']=d.score(pred)
            else:
                fold['by_recipe']={name:stats(errors[held & np.array([r['setting']==name for r in d.rows])])
                                  for name in sorted(set(r['setting'] for r in d.rows))}
            folds.append(fold);dump('calibration-progress.json',dict(results=results,current_family=family,folds=folds))
            print(family,page,'train',round(fold['train']['rmse'],3),'validation',round(fold['held']['rmse'],3),flush=True)
        results[family]=dict(config=cfg,folds=folds,cv_mse=float(np.mean([f['held_mse'] for f in folds[:4]])))
        dump('calibration.json',results)
    choice=min(results,key=lambda k:results[k]['cv_mse'])
    chosen=results[choice]['folds'][-1]
    model=dict(schema='bluecyan-conditional-sector-response/1',unit='MOUNT',iso=200,
        family=choice,kind=FAMILIES[choice]['kind'],parameters=chosen['parameters'],
        selection='minimum mean leave-one-T-page-out D50 DE00 squared error; V/card excluded',
        train_pages=['T1','T2','T3','T4'],train_recipes=sorted(set(r['setting'] for r in d.rows)),
        cv_mse={k:v['cv_mse'] for k,v in results.items()},
        stock04='unchanged; calibrates only ratio of recipe response to stock response',
        formula='base=ci*(W0@S); co=base*(1+sum(Wphi*g*S*(Zeff-1))/(Wphi@S))',
        sources={str(p.relative_to(ROOT)):a.sha(p) for p in [Path(__file__),e.Path(e.__file__),a.Path(a.__file__),
                 a.NOON/'all-patches.json',ROOT/'research/hue_ring/local/ring_model_v2.json']},
        tuning_data='T only; historical private photos, probe2/3, V and card not used to estimate parameters',
        full_hardware_pixel_model=False)
    dump('model.json',model)
    dump('model-holdout.json',chosen['scores'])
    print('selected',choice,'CV MSE',model['cv_mse'],flush=True)


if __name__=='__main__':main()
