"""Reconstruct the saved integer models and rescore the actual held-out artifacts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import time
import runtime as rt
from runtime import np, LOCAL
from run import load_arrays,training_objective
from ceiling_model import Problem,variants
from quality import fixtures,diagnostics

def close(a,b,path=''):
    if isinstance(b,dict):
        for k,v in b.items():
            if k in ('per_photo','label'):continue
            close(a[k],v,path+'/'+k)
    elif isinstance(b,list):
        assert len(a)==len(b),path
        for i,v in enumerate(b):close(a[i],v,path+'/'+str(i))
    elif b is None or isinstance(b,(str,bool)):
        assert a==b,(path,a,b)
    else:
        assert abs(float(a)-float(b))<2e-8,(path,a,b)

def integer_fields(p,allow_nonmonotone=False):
    keys=('curve_x_u12','curve_y_u8','matrix_q10','matrix_offset_integer_hypothesis',
          'sector_a','sector_b','sector_cd','c120_nodes_u14','c120_gains_u8',
          'c004_signed_integer','rlut_input_u12','rlut_output_u12')
    for key in keys:
        a=np.asarray(p[key]);assert np.isfinite(a).all() and np.array_equal(a,np.rint(a)),key
    q=np.asarray(p['curve_y_u8']);r=np.asarray(p['rlut_output_u12'])
    xs=np.asarray(p['curve_x_u12']);assert xs[0]==0 and xs[-1]==4095 and (np.diff(xs)>0).all()
    assert q.min()>=0 and q.max()<=255
    assert r.min()>=0 and r.max()<=4095
    if not allow_nonmonotone:
        assert (np.diff(q,axis=1)>=0).all() and (np.diff(r,axis=1)>=0).all()
    assert abs(np.asarray(p['matrix_q10'])).max()<=2047
    for key in ('sector_a','sector_b','sector_cd','c004_signed_integer'):
        assert abs(np.asarray(p[key])).max()<=127,key
    assert min(p['c120_gains_u8'])>=0 and max(p['c120_gains_u8'])<=255

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--indices',default='0:51')
    ap.add_argument('--skip-quality',action='store_true');args=ap.parse_args()
    aa,bb=map(int,args.indices.split(':'));started=time.monotonic()
    expected_quality=rt.read(rt.HERE/'primary_quality.json')
    protocol=rt.read(rt.HERE/'protocol.json')
    train_paths=set(protocol['train_photos']);held_paths={p for pp in protocol['holdout_photos'].values() for p in pp}
    assert not train_paths&held_paths and len(train_paths)==3 and len(held_paths)==17
    total=groups_checked=pixels=quality_checked=0;profiles=[]
    for i in range(aa,bb):
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz')
        gg={k:load_arrays(LOCAL/meta.get('group_files',{}).get(k,'samples_'+k+'.npz'))
            for k in ('train','synthetic','a12-50','a12-28','mount-a12')}
        c=rt.camera_for_unit(meta.get('camera_ui',0));gradients,rings=fixtures(c)
        keys=[]
        for cfg in variants():
            key=cfg['key']+('_fullfields' if cfg['level']>=2 else '')
            path=LOCAL/'fits'/f'{i:02d}'/(key+'.json')
            doc=rt.read(path);predictions=load_arrays(path.with_suffix('.npz'))
            p=doc['parameters'];integer_fields(p)
            P=Problem(c,gg['train']['x'],data['train_target'],gg['train']['sw'],doc['config'])
            s=P.unpack(p)
            direct=P.predict_state(P.state(np.asarray(doc['theta']),True),gg['train']['x'])
            assert np.array_equal(direct,predictions['train']),(i,key,'theta vs integer state')
            for group,g in gg.items():
                if not len(g['x']):assert doc['scores'][group] is None;continue
                actual=P.predict_state(s,g['x'])
                assert np.array_equal(actual,predictions[group]),(i,key,group,'saved prediction differs')
                score=rt.score(data[group+'_base'],actual,data[group+'_target'])
                close(score,doc['scores'][group],f'{i}/{key}/{group}')
                if 'per_photo' in doc['scores'][group]:
                    for photo_id in np.unique(g['photo_id']):
                        mask=g['photo_id']==photo_id
                        ps=rt.score(data[group+'_base'][mask],actual[mask],data[group+'_target'][mask])
                        close(ps,doc['scores'][group]['per_photo'][str(photo_id)],f'{i}/{key}/{group}/photo{photo_id}')
                groups_checked+=1;pixels+=len(actual)
            obj=training_objective(data['train_base'],predictions['train'],data['train_target'],gg['train']['sw'])
            assert abs(obj-doc['train_objective'])<2e-8,(i,key,'objective')
            if not args.skip_quality:
                quality=diagnostics(c,lambda x,r:P.predict_state(s,x,r),gradients,rings)
                close(quality,expected_quality[f'{i:02d}/{key}'],f'{i}/{key}/quality')
                quality_checked+=1
            keys.append(key);total+=1
        assert len(keys)==30 and len(set(keys))==30
        profiles.append(dict(index=i,name=meta['name'],primary_fits=len(keys)))
        print('Verified integer states and scores',i,flush=True)
    result=dict(label='电脑预测，离线结果复核',indices=[aa,bb],primary_fits=total,
        scored_groups=groups_checked,pixels_reconstructed=pixels,quality_fixtures_recomputed=quality_checked,
        integer_parameters_verified=True,saved_predictions_byte_equal=True,score_tolerance=2e-8,
        profiles=profiles,seconds=time.monotonic()-started,
        hardware_acceptance=False,camera_or_card_access=False)
    rt.dump(LOCAL/f'verification_{aa:02d}_{bb:02d}.json',result)
    rt.finish(f'verify_{aa}_{bb}')

if __name__=='__main__':main()
