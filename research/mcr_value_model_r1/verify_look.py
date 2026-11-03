"""Recompute isolated stage errors directly from saved integer matrices."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
study=rt.module('verify_look_study',rt.HERE/'look_study.py')
YCC=study.YCC


def main():
    m=rt.model()
    maximum=0.
    checked=0
    for slot in ('01','02'):
        a=rt.arrays(f'research/gr4_analytic_target_r2/local/data/{slot}.npz')
        c=study.pp.common()
        mode=study.pp.MODES[slot]
        metadata=rt.read('research/gr4_analytic_target_r2/local/gxrdng_metadata.json')
        exact=rt.sim.render_scene(a['scene'],mode,c)
        curve=rt.sim.curve(mode,c['gain'])
        unique,index=np.unique(curve,return_index=True)
        for fold in study.vm.FOLDS:
            d=study.vm.data(m,slot,fold,'diagnostic')
            doc=rt.read(rt.LOCAL/f'look_study/{slot}/{fold}.json')
            saved=rt.arrays(rt.LOCAL/f'look_study/{slot}/{fold}.npz')
            assert set(map(tuple,doc['train_keys'])).isdisjoint(map(tuple,doc['held_keys']))
            for hypothesis,result in doc['models'].items():
                assert result['success'] and result['integer_valid']
                M=np.asarray(result['mix_q10'])/1024
                B=np.linalg.inv(YCC)@(np.asarray(result['post_ycc_q10'])/1024)
                raw=d['raw_wb']
                if hypothesis=='H3': raw=(raw/d['wb'])@M.T*d['wb']
                else: raw=raw@M.T
                scene=np.empty_like(raw)
                for k,r in enumerate(d['records']):
                    info=metadata[r['frame']]
                    scene[k]=raw[k]@np.asarray(info['raw_wb_to_scene_without_BE']).T*2**info['baseline_exposure']
                z,_=study.pp.front(scene,mode,c)
                after=np.clip(study.pp.tone(z,mode,c)@B.T,0,1)
                before=np.interp(after,unique,(np.arange(256)*16/4095)[index])
                pred=np.clip(study.pp.tone(rt.sim.multiaxial(before,mode,rt.sim.Options()),mode,c),0,1)
                error=rt.cm.delta_e00(study.lab(pred),study.lab(exact))
                difference=float(abs(error-saved[hypothesis]).max())
                maximum=max(maximum,difference)
                assert difference<1e-8,(slot,fold,hypothesis,difference)
                checked+=1
    rt.dump('verification/look_reconstruction.json',dict(models=checked,
        maximum_de00_difference=maximum,all_ok=True,evidence='电脑预测'))
    doc=rt.read(rt.HERE/'verification.json')
    doc['isolated_look_models']=checked
    doc['isolated_look_maximum_de00_difference']=maximum
    rt.dump(rt.HERE/'verification.json',doc)
    rt.finish('verify_look')
    print(json.dumps(dict(models=checked,maximum_de00_difference=maximum,all_ok=True)),flush=True)


if __name__=='__main__':main()
