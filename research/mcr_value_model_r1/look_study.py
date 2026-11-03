"""Isolated look-stage study in the frozen analytic scene coordinate."""
from pathlib import Path
import csv
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from scipy.optimize import least_squares
original_dump = rt.dump


def parameter_dump(path, value):
    if str(path) == 'parameters.json':
        value = {key: value[key] for key in ('modes', 'gamma', 'sector_edges')}
    return original_dump(path, value)


rt.dump = parameter_dump
vm = rt.module('look_value_model', rt.HERE / 'model.py')
rt.sim = rt.module('look_simulator', 'research/gr4_analytic_target_r1/simulator.py')
pp = rt.module('look_pipeline', 'research/gr4_analytic_target_r2/pipeline.py')
YCC = np.array([[.299,.587,.114],[-.168736,-.331264,.5],[.5,-.418688,-.081312]])


def lab(rgb):
    return rt.cm.xyz_lab(rt.cm.srgb_decode(np.clip(rgb,0,1)) @ rt.cm.SRGB_XYZ.T,rt.cm.D65)


def neutral(values):
    M = np.eye(3)
    for v,(i,j) in zip(values,vm.PAIRS):
        M[i,j] += v
        M[i,i] -= v
    return M


def one(m,slot,fold):
    path=rt.LOCAL/f'look_study/{slot}/{fold}.json'
    if path.exists(): return rt.read(path)
    d=vm.data(m,slot,fold,'diagnostic')
    a=rt.arrays(f'research/gr4_analytic_target_r2/local/data/{slot}.npz')
    previous=rt.read(f'research/gr4_analytic_target_r2/local/decomposition_v2/{slot}/{fold}_parameters.json')
    metadata=rt.read('research/gr4_analytic_target_r2/local/gxrdng_metadata.json')
    c,mode=pp.common(),pp.MODES[slot]
    z,L=pp.front(a['scene'],mode,c)
    front=np.empty((len(z),3,3))
    for k,r in enumerate(d['records']):
        meta=metadata[r['frame']]
        front[k]=np.asarray(c['matrix']) @ np.linalg.inv(c['raw_wb_to_scene']) @ np.asarray(meta['raw_wb_to_scene_without_BE']) * 2**(c['exposure_ev']+meta['baseline_exposure'])
    assert np.max(abs(np.einsum('nij,nj->ni',front,d['raw_wb'])-z)) < 1e-12
    exact=rt.sim.render_scene(a['scene'],mode,c)
    noMA=pp.tone(z@L.T,mode,c)
    target_lab=lab(noMA)
    B0=np.linalg.inv(YCC) @ (np.asarray(previous['look_post_matrix_q10'])/1024)
    curve=rt.sim.curve(mode,c['gain'])
    unique,index=np.unique(curve,return_index=True)
    def inverse(v):
        return np.interp(np.clip(v,0,1),unique,(np.arange(256)*16/4095)[index])
    def restore(v):
        return np.clip(pp.tone(rt.sim.multiaxial(inverse(v),mode,rt.sim.Options()),mode,c),0,1)
    held=d['held']
    old_approx=np.clip(pp.tone(z,mode,c)@B0.T,0,1)
    old_error=rt.cm.delta_e00(lab(restore(old_approx)),lab(exact))
    stored=rt.arrays(f'research/gr4_analytic_target_r2/local/decomposition_v2/{slot}/{fold}_look_GXR_post.npz')
    assert np.max(abs(old_error[held]-stored['distortion'][held])) < 1e-9
    outputs={'previous':old_error}
    docs={}
    for hypothesis in ('post_only','H1','H2','H3'):
        n=6 if hypothesis=='post_only' else 12
        def state(p,quant=False):
            B=B0+neutral(p[:6]/256)-np.eye(3)
            C=YCC@B*1024
            if quant:
                C=np.rint(C)
                C[:,1]+=np.array([1024,0,0])-C.sum(axis=1)
                B=np.linalg.inv(YCC)@(C/1024)
            M=np.eye(3)
            if n==12:
                values=p[6:]/256
                if quant: values=np.rint(values*1024)/1024
                if hypothesis=='H2': M=neutral(values)
                else:
                    for v,(i,j) in zip(values,vm.PAIRS): M[i,j]=v
            return M,B,C
        def predict(p,quant=False):
            M,B,C=state(p,quant)
            r=d['raw_wb']
            if hypothesis=='H3': r=(r/d['wb'])@M.T*d['wb']
            else: r=r@M.T
            zz=np.einsum('nij,nj->ni',front,r)
            return np.clip(pp.tone(zz,mode,c)@B.T,0,1)
        def objective(p):
            components=m.fs.de00_components(lab(predict(p)),target_lab)[d['train']].ravel()
            M,B,C=state(p)
            limits=np.array([2047.,1279.,1279.])[:,None]
            overflow=np.maximum(abs(C)-limits,0).ravel()/32
            return np.r_[components,p*.0001,overflow]
        initial=np.zeros(n)
        bound=np.r_[np.full(6,256.),np.full(n-6,64.)]
        result=least_squares(objective,initial,bounds=(-bound,bound),max_nfev=180,
            ftol=2e-7,xtol=2e-7,gtol=2e-7,x_scale='jac')
        p=result.x
        no_ma_pred=predict(p,True)
        pred=restore(no_ma_pred)
        error=rt.cm.delta_e00(lab(pred),lab(exact))
        M,B,C=state(p,True)
        valid=bool(abs(C).max()<=2047 and abs(C[1:]).max()<=1279)
        assert valid
        outputs[hypothesis]=error
        docs[hypothesis]=dict(theta=p,mix_q10=np.rint(M*1024).astype(int),post_ycc_q10=C.astype(int),
            success=bool(result.success),nfev=int(result.nfev),cost=float(result.cost),integer_valid=valid,
            held_median=float(np.median(error[held])),training_only=True,
            isolated_analytic_stage=True,camera_verified=False)
    rt.dump(path,dict(slot=slot,fold=fold,evidence='电脑预测',target_label='未验证目标，仅诊断',
        models=docs,train_keys=d['train_keys'],held_keys=d['held_keys'],
        assumptions='固定解析共同前级和完整目标曲线；只拟合前置混色与后置保中性矩阵'))
    np.savez_compressed(path.with_suffix('.npz'),**outputs,held=held)
    print(json.dumps(dict(study='look',slot=slot,fold=fold,
        scores={h:round(v['held_median'],4) for h,v in docs.items()})),flush=True)


def aggregate():
    rows=[]
    for slot in ('01','02'):
        for scheme,folds in [('page',vm.FOLDS[:6]),('hue',vm.FOLDS[6:])]:
            aa=[rt.arrays(rt.LOCAL/f'look_study/{slot}/{f}.npz') for f in folds]
            cat=lambda key:np.concatenate([a[key][a['held']] for a in aa])
            previous=float(np.median(cat('previous')))
            post=float(np.median(cat('post_only')))
            for h in ('H1','H2','H3'):
                e=float(np.median(cat(h)))
                rows.append(dict(evidence='电脑预测',slot=slot,scheme=scheme,hypothesis=h,
                    previous_projection_de00=previous,optimized_post_only_de00=post,
                    pre_and_post_de00=e,recovered_previous_fraction=1-e/previous,
                    recovered_optimized_post_fraction=1-e/post,
                    additional_reduction_de00=post-e))
    rt.dump('look_summary.json',rows)
    with (rt.HERE/'look_scores.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    m=rt.model()
    for slot in ('01','02'):
        for fold in vm.FOLDS: one(m,slot,fold)
    rows=aggregate()
    print(json.dumps(rows,ensure_ascii=False),flush=True)
    rt.finish('look_study')


if __name__=='__main__': main()
