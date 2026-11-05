"""Position cost for digital styles and the official Acros independent-curve control."""
import argparse
import itertools
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,ROOT,LOCAL,UNITS,read,dump,predict,arrays,sha
A=C.module('film_r2_score_adapter',LOCAL.parent/'analyze.py')


def run(index,unit):
    ui=UNITS.index(unit)
    if index==53:
        left=LOCAL/'fits'/unit/'14/exact.json';right=LOCAL/'fits'/unit/'4053/exact.json'
        meta=read(LOCAL/'targets'/unit/'14/profile.json');name='Acros official'
    else:
        left=LOCAL/'fits'/unit/f'{3000+index*10:02d}/exact.json'
        right=LOCAL/'fits'/unit/f'{3001+index*10:02d}/exact.json'
        meta=read(LOCAL/'targets'/unit/f'{3000+index*10:02d}/profile.json');name=meta['name']
    docs=[read(left),read(right)];entries=[Path(d['record_file']).read_bytes() for d in docs]
    assert entries[0][1]==1 and entries[1][1]==7,'Shared/full C100 flags must be1/7'
    literal=C.module('film_style_literal',C.frozen('research/bluecyan_r1/verify.py')).predict_literal
    bank={g:arrays(p) for g,p in meta['groups'].items()};results=[];preds=[]
    for doc,b in zip(docs,entries):
        assert sha(doc['record_file'])==doc['record_sha256'] and doc['nice']==15
        checks=C.codec.record_checks(b);assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
        ordinary=bytearray(b);ordinary[0]=1
        scores={};outputs={};maximum=0.
        for group,v in bank.items():
            out=predict(b,v['x'],ui);reference=literal(C.model(ui),bytes(ordinary),v['x'])
            maximum=max(maximum,float(abs(out-reference).max()));assert maximum<1e-8
            outputs[group]=out;scores[group]=A.score_group(v,out)
        preds.append(outputs)
        results.append(dict(record_file=doc['record_file'],record_sha256=doc['record_sha256'],
            flags=b[1],base_slot=b[0],record_bytes=552,scores=scores,quality=doc['quality'],
            reference_exact_checked=True,exact_starts=len(doc['starts']),
            all_starts_converged=all(a['receipt']['success'] for a in doc['attempts']),
            literal_RGB_maximum_difference=maximum,checks=checks))
    v=bank['photo_iso200'];a,b=[x['scores']['photo_iso200'] for x in results]
    gap=None if a['similarity_percent'] is None or b['similarity_percent'] is None else b['similarity_percent']-a['similarity_percent']
    penalty=a['de00']['median']-b['de00']['median'];quant=[]
    for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
        for phase in itertools.product((0.,.25,.5,.75),repeat=3):
            left=C.ba.phase_output(preds[0]['photo_iso200'],np.asarray(phase),order,rt.mm)
            right=C.ba.phase_output(preds[1]['photo_iso200'],np.asarray(phase),order,rt.mm)
            s0,s1=[rt.score(v['base_new'],p,v['want']) for p in (left,right)]
            d=None if s0['similarity_percent'] is None or s1['similarity_percent'] is None else s1['similarity_percent']-s0['similarity_percent']
            absolute=s0['de00']['median']-s1['de00']['median']
            ok=(d is None or d<2) and absolute<=.25
            quant.append(dict(order=order,phase=phase,Look_safe=bool(ok),full_minus_Look_pp=d,Look_extra_de00=absolute))
    safe=(gap is None or gap<2) and penalty<=.25 and all(q['Look_safe'] for q in quant) and results[0]['quality']['passes']
    result=dict(classification_revision='2pp_median025_quant128',index=index,unit=unit,name=name,Look=results[0],full=results[1],
        full_minus_Look_pp=gap,Look_extra_median_de00=penalty,
        quantization_Look_safe_branches=sum(q['Look_safe'] for q in quant),quantization_branches=128,
        quantization=quant,Look_safe=bool(safe),no_candidate_camera_exposures=True,
        classification_scope='Fixed declared target, native C040, training-selected integer fits, photo holdout and 128 output quantization hypotheses')
    dump(LOCAL/'style_analysis'/f'{index:02d}'/(unit+'.json'),result)
    print('STYLE ANALYZED',name,unit,'Look/full',a['similarity_percent'],b['similarity_percent'],
        'gap',gap,'safe',safe,'quant',result['quantization_Look_safe_branches'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);p.add_argument('--unit',choices=UNITS,required=True)
    args=p.parse_args();run(args.index,args.unit)
