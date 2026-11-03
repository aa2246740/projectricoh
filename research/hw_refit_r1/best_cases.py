"""Record a per-recipe optimistic envelope; field-unit assumptions may conflict."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import *
from report import summary,best,lower,canonical_route,write_csv
from verify import packed_predict


def location(slot,route):
    if route.startswith('u06_'):root=rt.LOCAL/'unfrozen06'
    elif route.startswith(('r96_','r128_')):root=rt.LOCAL/('c120_radius/R'+route.split('_',1)[0][1:])
    else:root=rt.LOCAL
    return root,canonical_route(route)


def main():
    rows,ix=summary()
    units=rt.read(rt.HERE/'offset_unit_sensitivity.json')
    unit_index={(r['slot'],r['route'],r['units'],r['scheme']):r for r in units['rows']}
    variants={v[0]:(v[1],v[2]) for v in units['variants']}
    pairs={}
    for r in units['rows']:
        if r['scheme'] in ('page','hue') and r['tint_code_valid'] and 'RLUT' not in r['route']:
            pairs.setdefault((r['slot'],r['route'],r['units']),{})[r['scheme']]=r['similarity']
    m=rt.model();result=[];max_error=0.
    for slot in ('05','06','01','02'):
        primary=best(ix,slot,[r['route'] for r in rows if r['slot']==slot and 'RLUT' not in r['route']])
        candidates=[(min(v.values()),k[1],k[2]) for k,v in pairs.items() if k[0]==slot and len(v)==2]
        value,route,unit=max(candidates)
        use_unit=value>lower(ix,slot,primary)+1e-12
        if not use_unit:route,unit=primary,'primary_integer'
        root,name=location(slot,route)
        collected=[]
        for fold in [f'page{i}' for i in range(1,7)]+[f'hue{i}' for i in range(3)]+['full']:
            d=prepare_data(m,slot,fold)
            base=rt.read(root/f'fits/{slot}/{name}/{fold}.json')
            if use_unit:
                if 'scope_variant' in base:
                    from unfrozen06 import UnfrozenProblem
                    P=UnfrozenProblem(m,slot,d,base['features'],base['daily'])
                else:P=Problem(m,slot,d,base['features'],base['daily'])
                p=np.array(base['theta']);packed=packed_parameters(P,p)
                out_unit,tint_unit=variants[unit]
                if 'offsets' in P.blocks:packed['output_input_offset_delta']=np.rint(P.val(p,'offsets')/out_unit).astype(int)
                tint=next((k for k in ('tint_add','tint_Y') if k in P.blocks),None)
                if tint:packed['c004_signed_magnitude_delta']=np.rint(P.val(p,tint)/tint_unit).astype(int)
                doc=dict(base,packed=packed,c100_delta_unit=out_unit,c004_delta_unit=tint_unit)
            else:
                ref=root/f'integer_refined/{slot}/{name}/{fold}.json'
                doc=rt.read(ref) if ref.exists() else base
            pred=packed_predict(m,slot,d,doc)
            e=m.fs.delta_e00(m.fs.lab_from_codes(pred),d['target'])
            held=d['held'] if fold!='full' else d['score_mask']
            gray=np.array([r['key'].startswith('GRAY_') or r['key'] in ('ANCHOR_white','ANCHOR_black','ANCHOR_midgray','ANCHOR_darkgray','ANCHOR_lightgray') for r in d['records']])&held
            dest=rt.LOCAL/f'best_cases/{slot}/{fold}.json'
            rt.dump(dest,dict(slot=slot,route=route,units=unit,fold=fold,features=base['features'],packed=doc['packed'],
                             c100_delta_unit=doc.get('c100_delta_unit',1.),c004_delta_unit=doc.get('c004_delta_unit',1.),
                             score=score(e[held],d['baseline'][held]),gray=score(e[gray],d['baseline'][gray]),
                             prediction_label='电脑预测',heldout_selected_route=True,not_one_jointly_verified_hardware_unit=True))
            np.savez_compressed(dest.with_suffix('.npz'),prediction=pred,error=e,held=held,gray=gray,baseline=d['baseline'])
            collected.append((fold,e,held,gray,d['baseline']))
        out=dict(slot=slot,route=route,units=unit,label='电脑预测',shared_hardware_units_proven=False)
        for scheme in ('page','hue','full'):
            aa=[r for r in collected if (r[0].startswith(scheme) if scheme!='full' else r[0]=='full')]
            ee=np.concatenate([r[1][r[2]] for r in aa]);bb=np.concatenate([r[4][r[2]] for r in aa])
            gg=np.concatenate([r[1][r[3]] for r in aa]);gb=np.concatenate([r[4][r[3]] for r in aa])
            out[scheme]=score(ee,bb);out[scheme]['gray']=score(gg,gb)
            if use_unit:
                expected=unit_index[slot,route,unit,scheme]['similarity']
            else:expected=ix[slot,route,scheme]['integer']['similarity']
            max_error=max(max_error,abs(out[scheme]['similarity']-expected))
        result.append(out)
    assert max_error<1e-8
    rt.dump(rt.HERE/'best_cases.json',dict(rows=result,score_replay_max_error=max_error,
            caveat='per-recipe most favourable tested field units; not a simultaneously established hardware setting; exploratory selection'))
    write_csv('best_cases.csv',[dict(slot=r['slot'],route=r['route'],units=r['units'],scheme=s,label='电脑预测',**r[s]) for r in result for s in ('page','hue','full')])
    rt.finish('best_cases')
    print(rt.plain(result),flush=True)


if __name__=='__main__':main()
