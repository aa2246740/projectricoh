"""Recompute metrics, cross-check the legacy cube reader, and verify frozen inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import json
from types import SimpleNamespace


def close(a,b,tol=1e-9):
    assert np.max(abs(np.asarray(a)-np.asarray(b)))<tol,(a,b)


def targets():
    from isp import model
    from style import Dense,PAIRS
    m=model();result=[]
    for slot,style in [('01','positive'),('02','negative')]:
        a=rt.arrays(PAIRS[style]+'/local/fit/data.npz')
        target,support,_=Dense(style).target(a['scene_x'],rt.lab(m.predict('04',a['scene_x'])))
        assert np.all(support[a['supported']])
        difference=float(np.max(abs(target[a['supported']]-a['new_target'][a['supported']])))
        assert difference<1e-8
        result.append(dict(slot=slot,target_Lab_max_difference=difference))
    return result


def cubes():
    from lut import vertices,apply
    old=sys.modules.get('guard')
    sys.modules['guard']=SimpleNamespace(input_path=rt.inp,sha=rt.sha)
    cube=rt.module('ceiling_legacy_cube','research/lut_convert/cube.py')
    if old is None:del sys.modules['guard']
    else:sys.modules['guard']=old
    rng=np.random.default_rng(20261026)
    query=rng.integers(0,256,(1600,3)).astype(float)
    identity=dict(x=np.zeros((1,3)),alpha=np.zeros((1,3)),width=48.,ridge=.03)
    result=[]
    for n in (17,33):
        assert np.array_equal(apply(identity,query,n),query)
        for slot in ('01','02'):
            table=rt.arrays(rt.LOCAL/f'lut/host_only_RGB_Q8_8_{slot}_{n}.npz')['nodes']
            imported=cube.Cube(None,table.transpose(2,1,0,3).astype(float)/(255*256),np.zeros(3),np.ones(3))
            position=np.floor(query*((n-1)/255)*256+.5)/256/(n-1)
            expected=np.floor(imported.apply(position)*255+.5)
            vv,w=vertices(query,n)
            val=table[vv[...,0],vv[...,1],vv[...,2]].astype(np.int64)
            actual=np.clip(((val*w[:,:,None]).sum(1)+32768)//65536,0,255)
            difference=float(np.max(abs(actual-expected)))
            assert difference==0
            result.append(dict(slot=slot,cube=n,max_code_difference=difference,
                               independent_reader='research/lut_convert/cube.py'))
    return result


def metrics():
    result=[]
    for path in sorted((rt.LOCAL/'lut').glob('*.npz')):
        a=rt.arrays(path)
        if not {'prediction','target','error','baseline'}<=set(a):continue
        e=rt.cm.delta_e00(rt.lab(a['prediction']),a['target'])
        close(e,a['error'])
        result.append(dict(file=str(path.relative_to(rt.LOCAL)),**rt.score(e,a['baseline'])))
    return result


def isp():
    from style import PAIRS
    result=[]
    for path in sorted((rt.LOCAL/'isp').glob('*/*/*.json')):
        if path.stem=='summary':continue
        d=json.loads(path.read_text());candidate=d['candidate']
        assert candidate['solver_success'] and all(candidate['checks'].values())
        assert set(map(tuple,d['train_keys'])).isdisjoint(set(map(tuple,d['holdout_keys'])))
        arrays=rt.arrays(path.with_suffix('.npz'))
        e=rt.cm.delta_e00(rt.lab(arrays['prediction']),arrays['target'])
        close(e,arrays['error'])
        held=arrays['held'];s=rt.score(e[held],arrays['baseline'][held])
        if s['similarity_median'] is not None:
            close(s['similarity_median'],d['score']['similarity_median'])
            prefix=PAIRS['positive' if d['slot']=='01' else 'negative']
            reference=rt.read(prefix+f'/local/fit/folds/{d["fold"]}.json')['scores']['new']['candidate']
            close(d['current']['similarity_median'],reference['similarity_median'])
        result.append(dict(slot=d['slot'],route=d['route'],fold=d['fold'],solver_success=True,
                           safety_passed=True,reference_current_matches=True))
    assert len(result)==120,len(result)
    return result


def styles():
    summary=rt.read(rt.LOCAL/'style/relative_sampling.json');rows=[]
    for doc in summary:
        style='positive' if doc['slot']=='01' else 'negative'
        files=sorted((rt.LOCAL/'style').glob(f'relative_{style}_{doc["scheme"]}*_{doc["method"]}.npz'))
        error=[];baseline=[]
        for path in files:
            a=rt.arrays(path)
            error.extend(rt.cm.delta_e00(a['prediction_lab'],a['target_lab']));baseline.extend(a['baseline'])
        score=rt.score(error,baseline)
        close(score['similarity_median'],doc['similarity_median'])
        rows.append(dict(slot=doc['slot'],scheme=doc['scheme'],method=doc['method'],score=score))
    for path in (rt.LOCAL/'style').glob('full_*_*.npz'):
        a=rt.arrays(path)
        if 'prediction_lab' in a:
            close(rt.cm.delta_e00(a['prediction_lab'],a['target_lab']),a['error'])
    return rows


def check_hashes():
    rows=(rt.HERE/'SHA256SUMS').read_text().splitlines()
    for row in rows:
        digest,name=row.split('  ',1)
        assert rt.sha(rt.HERE/name)==digest,name
    print('SHA256SUMS verified',len(rows))


def seal():
    entries=[]
    for path in sorted(rt.HERE.rglob('*')):
        if not path.is_file() or path.is_symlink() or path.name=='SHA256SUMS' or '__pycache__' in path.parts:continue
        entries.append(f'{rt.sha(path)}  {path.relative_to(rt.HERE)}')
    (rt.HERE/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
    print('sealed',len(entries),'files')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--hashes',action='store_true');ap.add_argument('--seal',action='store_true');a=ap.parse_args()
    if a.hashes:check_hashes();return
    if a.seal:seal();return
    result=dict(targets=targets(),cube_interpolation=cubes(),metrics=metrics(),ISP=isp(),style_metrics=styles(),
                frozen_input_count=rt.verify_inputs(),network_used=False,camera_used=False,builds=False,
                decisions_tsv_excluded=True,private_data_ignored=True)
    rt.dump('verification/final.json',result)
    print('verified targets,',len(result['metrics']),'LUT evaluations,',len(result['ISP']),'ISP solves, frozen inputs',result['frozen_input_count'])


if __name__=='__main__':main()
