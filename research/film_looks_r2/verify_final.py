"""Re-read final selected bytes, pixel scores and scene-neutral film diagnostics."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,LOCAL,UNITS,read,dump,sha,predict,arrays
import library as L
import host_flags
import promote_probe
A=C.module('film_verify_score_adapter',LOCAL.parent/'analyze.py')


def run(ordinal,unit):
    film=L.CATALOG['films'][ordinal];ui=UNITS.index(unit)
    path=LOCAL/'analysis'/f'{ordinal:02d}'/unit/'final.json';doc=read(path)
    assert doc['placement_classification_complete']
    root=LOCAL/'films'/f'{ordinal:02d}'/unit
    bank={p.stem:arrays(p) for p in root.glob('*.npz') if p.stem not in ('train_weighted','train_jpeg')}
    literal=C.module('film_final_literal',C.frozen('research/bluecyan_r1/verify.py')).predict_literal
    receipts=[];points=0;maximum=0.
    for route in (doc['selected_Look_route'],doc['selected_route']):
        record=doc['routes'][route];b=Path(record['record_file']).read_bytes()
        assert hashlib.sha256(b).hexdigest()==record['record_sha256'] and len(b)==552
        checks=C.codec.record_checks(b);assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
        assert record['reference_exact_checked']
        runtime_flags=host_flags.check(C,b,unit)
        promoted=promote_probe.promote(b,1<<ui,C.codec) if b[1]==1 and b[114]>=128 else None
        promoted_points=0;promoted_maximum=0.
        if b[1]==1:assert C.codec.look_identity_valid(b,1<<ui)
        assert struct.unpack_from('>H',b,445)[0]==(0 if b[1]&4 else 2)
        plain=bytearray(b);plain[0]=1;local_points=0;local_max=0.
        for key,v in bank.items():
            assert np.array_equal(C.input_codes(v['raw_codes'],unit),v['x'])
            expected=literal(C.model(ui),bytes(plain),v['x']);actual=predict(b,v['x'],ui)
            difference=float(abs(expected-actual).max());assert difference<1e-8
            if promoted is not None:
                padded=predict(promoted,v['x'],ui)
                change=float(abs(padded-actual).max());assert change==0.
                promoted_points+=len(padded);promoted_maximum=max(promoted_maximum,change)
            actual_score=rt.score(v['base_new'],np.rint(actual),v['want'])
            saved=record['scores'][key]
            for field in ('median','p95','max','mean'):
                assert abs(actual_score['de00'][field]-saved['de00'][field])<1e-10,(key,field)
            local_max=max(local_max,difference);local_points+=len(actual)
        receipts.append(dict(route=route,record_sha256=record['record_sha256'],row_domains_and_CRCs=True,
            points=local_points,maximum_literal_RGB_difference=local_max,saved_scores_recomputed=True))
        receipts[-1]['runtime_C_flags']=runtime_flags
        if b[1]==1 and promoted is None:
            receipts[-1]['shared_curve_flags7_unavailable']='Shared curve endpoint below128; cannot alias it into the existing type26 R/B domain'
        if promoted is not None:
            receipts[-1]['shared_curve_flags7_equivalence']=dict(points=promoted_points,
                maximum_RGB_difference=promoted_maximum,three_curves_identical=True,
                additional_curve_rows=0,extra_fitted_curve_parameters=0,
                promoted_sha256=hashlib.sha256(promoted).hexdigest())
            receipts[-1]['shared_curve_flags7_knobs']=host_flags.compare_shared_promotion(
                C,b,promoted,unit,bank['train']['x'][:64])
        points+=local_points;maximum=max(maximum,local_max)
    selected=doc['routes'][doc['selected_route']]
    target=L.FilmTarget(film)
    entry=Path(selected['record_file']).read_bytes();tone,chroma=A.features(unit,entry,target)
    doc['tone']=C.plain(tone);doc['brightness_dependent_color']=C.plain(chroma)
    diagnostics={}
    for route in ('scene_rgb_matrix','scene_structure','scene_shared_structure'):
        record=doc['routes'][route]
        b=Path(record['record_file']).read_bytes()
        assert hashlib.sha256(b).hexdigest()==record['record_sha256']
        t,c=A.features(unit,b,target)
        diagnostics[route]=dict(gray_shape=t['gray_shape'],
            supported_shoulder_de00=t['supported_shoulder_error_de00'],
            supported_color_de00=c['supported_input_de00'],
            supported_hue_degrees=c['supported_input_hue_error_degrees'],
            supported_relative_chroma_error_percent=c['supported_relative_chroma_error_percent'],
            brightness_dependent_hue_span_degrees=c['brightness_dependent_hue_span_degrees'],
            fixed_hue_reverse_intervals=record['quality']['reverse_hue_intervals'],
            fixed_hue_defined_intervals=record['quality']['hue_defined_intervals'],
            reference_exact_checked=record['reference_exact_checked'])
    doc['structure_comparison']=C.plain(diagnostics)
    for name,row in doc['routes'].items():
        source=read(Path(row['record_file']).with_suffix('.json'))
        assert source['record_sha256']==row['record_sha256']
        row.update(selected_origin=source['origin'],retained_unmodified_template=source['payload_bytes_changed']==0,
                   rejected_integer_candidates=sum(not x['quality']['passes'] for x in source['checks']))
    v=bank['photo_iso200']
    for key,usage in (('want_jpeg','jpeg'),('want_scene_srgb_control','scene_srgb_control'),
                      ('want_scene_default_control','scene_default_control')):
        control=v[key] if key in v else target(v['xyz'],v['base_new'],usage)
        e=rt.delta_e00(rt.lab_from_codes(control),rt.lab_from_codes(v['want']))
        doc['control_target_differences'][key]=C.plain(dict(target_difference_de00=rt.stats(e),
            same_fixed_scene_target_used_for_all_candidate_scores=True))
    stock_loss=A.weighted_loss(bank['train']['base_new'],bank['train'])
    doc['training_improved_vs_stock04']=selected['unweighted_integer_training_loss']<stock_loss-1e-9
    doc['primary_photo_improved_vs_baseline']=selected['scores']['photo_iso200']['de00']['median']<doc['existing_baseline_scores']['photo_iso200']['de00']['median']-1e-9
    dump(path,doc)
    result=dict(status='PASS',film=film['name'],ordinal=ordinal,unit=unit,records=receipts,
        points=points,maximum_literal_RGB_difference=maximum,gray_shape=tone['gray_shape'],
        runtime_C_flags_checked=True,
        no_DAT_or_device_acceptance=True,analysis_sha256=sha(path))
    dump(LOCAL/'final_verification'/f'{ordinal:02d}'/(unit+'.json'),result)
    print('FINAL REPLAY PASS',film['name'],unit,points,'points, gray drawdown',tone['gray_shape']['maximum_Lstar_drawdown'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--film',type=int,required=True);p.add_argument('--unit',choices=UNITS,required=True)
    args=p.parse_args();run(args.film,args.unit)
