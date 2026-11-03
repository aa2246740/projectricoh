"""Directional derivatives and exact L0/L1 equivalence against the old model."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np,LOCAL
from ceiling_model import Problem,variants

def main():
    c=rt.Camera()
    with np.load(LOCAL/'samples_train.npz') as z:
        x=z['x'][:121];sw=z['sw'][:121]
    with np.load(LOCAL/'target_00.npz') as z: want=z['train_target'][:121]
    rows=[]
    rng=np.random.default_rng(20261102)
    configs=list(variants())
    keys=['L0','L1','L2_Y_post','L2_C_pre','L3_Y_post_add_after','L3_C_pre_Y_before',
          'L4_Y_post_add_after_Rbefore','L4_C_pre_Y_before_Rafter',
          'L4_Y_post_add_after_Rbefore_physical','L4_C_pre_Y_before_Rafter_physical']
    configs += [{**c,'key':c['key']+'_physical','asym_kernel':'physical_linear_H1'}
                for c in configs if c['key'] in ('L4_Y_post_add_after_Rbefore','L4_C_pre_Y_before_Rafter')]
    full=[{**c,'key':c['key']+'_fullfields','full_fields':True,'asym_kernel':'physical_linear_H1'}
          for c in configs if c['key'] in ('L2_Y_post','L3_Y_post_add_after','L4_Y_post_add_after_Rbefore')]
    configs+=full;keys += [c['key'] for c in full]
    free=[{**c,'key':c['key']+'_free_check','full_fields':True,'free_curves':True}
          for c in configs if c['key'] in ('L1','L4_Y_post_add_after_Rbefore_fullfields')]
    configs+=free;keys += [c['key'] for c in free]
    for config in configs:
        if config['key'] not in keys: continue
        P=Problem(c,x,want,sw,config)
        p=P.theta0.copy()
        p[:2]+=[.02,-.01]
        p[2:26]+=.01*rng.normal(size=24)
        p[26:50]+=.01*rng.normal(size=24)
        p[P.qstart:P.qend]+=.17*rng.normal(size=P.qend-P.qstart)
        for k,sl in P.blocks.items():
            if k=='base':continue
            p[sl]=rng.normal(size=sl.stop-sl.start)*(.001 if k=='matrix' else .17)
        r,J=P.evaluate(p)
        for key,sl in P.blocks.items():
            d=np.zeros(P.np);d[sl]=rng.normal(size=sl.stop-sl.start)
            d/=np.linalg.norm(d)
            eps=2e-5
            numeric=(P.evaluate(p+eps*d)[0]-P.evaluate(p-eps*d)[0])/(2*eps)
            rel=float(np.linalg.norm(numeric-J@d)/max(np.linalg.norm(numeric),1e-10))
            rows.append(dict(config=config['key'],block=key,relative_error=rel))
            assert rel<.003,(config['key'],key,rel)
        if config['level']<=1 and not config.get('free_curves'):
            old=P.legacy.quantize(p)
            actual=P.predict_state(P.state(p,True),x,False)
            expected=P.legacy.predict(old['theta'],x)
            diff=float(np.max(abs(actual-expected)))
            rows.append(dict(config=config['key'],old_model_max_code_difference=diff))
            assert diff<1e-8,diff
        packed=rt.plain(P.packed(p))
        direct=P.predict_state(P.state(p,True),x,False)
        restored=P.predict_state(P.unpack(packed),x,False)
        assert np.max(abs(direct-restored))<1e-9
        print(config['key'],'checked',flush=True)
    rt.dump('model_checks.json',rows)
    rt.finish('model_checks')

if __name__=='__main__':main()
