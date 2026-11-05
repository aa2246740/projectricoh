"""Admit the weighted control separately, against both release and color budgets."""
import argparse
import itertools
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import library as L
import host_flags
import export as E

A=C.module('film_weighted_score_adapter',C.HERE/'analyze.py')


def run(ordinal,unit):
    summary=C.read(C.LOCAL/'summary.json');assert summary['complete']
    film=next(f for f in summary['films'] if f['ordinal']==ordinal)
    position=film['units'][unit];budget=position['weighted']
    assert budget['meets_color_and_overall_budget'] and budget['reference_exact']
    path=C.LOCAL/'analysis'/f'{ordinal:02d}'/unit/'final.json';doc=C.read(path)
    assert doc['analysis_revision']=='r3_unweighted_primary_weighted_control'
    primary=doc['routes'][doc['selected_route']];weighted=doc['routes']['scene_weighted']
    assert doc['selected_route'] in ('scene_rgb_matrix','scene_structure')
    assert weighted['reference_exact_checked'] and weighted['quality']['passes']
    entry=Path(weighted['record_file']).read_bytes();main=Path(primary['record_file']).read_bytes()
    assert C.sha(weighted['record_file'])==weighted['record_sha256'] and entry[1]==7
    root=C.LOCAL/'films'/f'{ordinal:02d}'/unit
    bank={p.stem:C.arrays(p) for p in root.glob('*.npz') if p.stem not in ('train_weighted','train_jpeg')}
    ui=C.UNITS.index(unit);old,oldinfo=A.baseline_record(unit,film['name'])
    outputs={label:{key:C.predict(b,v['x'],ui) for key,v in bank.items()}
             for label,b in (('old',old),('primary',main),('weighted',entry))}
    literal=C.module('film_weighted_literal',C.frozen('research/bluecyan_r1/verify.py')).predict_literal
    ordinary=bytearray(entry);ordinary[0]=1;maximum=0.;points=0
    for key,v in bank.items():
        reference=literal(C.model(ui),bytes(ordinary),v['x'])
        maximum=max(maximum,float(abs(reference-outputs['weighted'][key]).max()));points+=len(v['x'])
    assert maximum<1e-8
    native=host_flags.check(C,entry,unit)
    definition=L.CATALOG['films'][ordinal]
    meta=C.read(C.LOCAL/'targets'/unit/str(definition['indices']['scene_weighted'])/'profile.json')
    gate=C.load_assess().Gate(meta,bank,old)
    v=bank['photo_iso200'];regions=L.regions(v['xyz']);eligible={k:m for k,m in regions.items() if int(m.sum())>=20}
    target_lab=C.rt.lab_from_codes(v['want']);branches=[]
    for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
        for phase in itertools.product((0.,.25,.5,.75),repeat=3):
            ph=C.np.asarray(phase)
            before={k:C.ba.phase_output(outputs['old'][k],ph,order,C.rt.mm) for k in gate.rows}
            after={k:C.ba.phase_output(outputs['weighted'][k],ph,order,C.rt.mm) for k in gate.rows}
            reference=C.ba.phase_output(outputs['primary']['photo_iso200'],ph,order,C.rt.mm)
            result=gate.assess(before,after)
            scores=[C.rt.score(v['base_new'],p,v['want']) for p in (reference,after['photo_iso200'])]
            base_score=C.rt.score(v['base_new'],before['photo_iso200'],v['want'])
            admission=(result['passes'] and scores[1]['de00']['median']<=base_score['de00']['median']+1e-10 and
                       scores[1]['de00']['p95']<=base_score['de00']['p95']+.25+1e-10)
            delta=scores[1]['similarity_percent']-scores[0]['similarity_percent']
            p95=scores[1]['de00']['p95']-scores[0]['de00']['p95']
            errors=[C.rt.delta_e00(C.rt.lab_from_codes(p),target_lab) for p in (reference,after['photo_iso200'])]
            changes={k:float(C.np.median(errors[1][m])-C.np.median(errors[0][m])) for k,m in eligible.items()}
            colors=bool(changes and delta>=-1 and p95<=.25 and sum(changes.values())<-.05 and
                        all(x<=.25 for x in changes.values()))
            branches.append(dict(order=order,phase=phase,release_gate_pass=bool(admission),
                color_and_overall_budget_pass=colors,passes=bool(admission and colors),
                similarity_change_pp=delta,p95_change_de00=p95,color_change_de00=changes,
                failures=result['failures']))
    train=bank['train'];improves=A.weighted_loss(outputs['weighted']['train'],train)<A.weighted_loss(train['base_new'],train)-1e-9
    admitted=bool(improves and all(b['passes'] for b in branches))
    costs={}
    for profile in ('release','test'):
        slots,looks=E.layout(profile);baseline=E.count(slots,looks)['row_pool_bytes']
        slots={u:dict(rows) for u,rows in slots.items()};slots[unit][6]=entry
        costs[profile]=E.count(slots,looks)['row_pool_bytes']-baseline
    exported=None
    if admitted:
        dest=C.LOCAL/'full_library/weighted_optional_v1'/film['id']/unit/'recipe.record552'
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==entry
        else:dest.write_bytes(entry)
        exported=str(dest)
    C.dump(C.LOCAL/'weighted_verification'/f'{ordinal:02d}'/(unit+'.json'),dict(
        schema='gxr-weighted-control-admission/1',film=film['name'],ordinal=ordinal,unit=unit,
        primary_record_sha256=primary['record_sha256'],record_sha256=weighted['record_sha256'],
        record_file=weighted['record_file'],optional_export=exported,record_bytes=552,flags=7,
        canonical_owner_slot=6,type26_control=0,primary_model_ISO=200,
        installation_contract='studio_installation_contract.json',
        source=dict(id=definition['id'],provider=definition['provider'],author=definition['author'],
            license=definition['license'],source_url=definition['source_url'],
            source_sha256=definition['scene']['sha256'],print_step=definition['print_step'],
            modifications='Perceptual training weights 2.5 for fixed skin/sky/foliage Lab regions; same fixed scene target and native-C040 camera pipeline'),
        reference_exact_checked=True,quality_pass=True,unweighted_training_improves_stock04=improves,
        existing_baseline=oldinfo,branches=branches,quantization_branches=128,
        release_gate_passes=sum(b['release_gate_pass'] for b in branches),
        color_budget_passes=sum(b['color_and_overall_budget_pass'] for b in branches),
        combined_passes=sum(b['passes'] for b in branches),robust_optional_model_candidate=admitted,
        literal_points=points,maximum_literal_RGB_difference=maximum,runtime_C_flags=native,
        net_row_pool_bytes_if_replacing_only_slot06=costs,nominal_color_budget=budget,
        analysis_sha256=C.sha(path),no_new_blind_photo_or_camera_acceptance=True,
        primary_library_remains_unweighted=True))
    print('WEIGHTED',film['name'],unit,'release',sum(b['release_gate_pass'] for b in branches),
          'color',sum(b['color_and_overall_budget_pass'] for b in branches),
          'combined',sum(b['passes'] for b in branches),'optional',admitted,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--film',type=int,required=True)
    parser.add_argument('--unit',choices=C.UNITS,required=True);args=parser.parse_args();run(args.film,args.unit)
