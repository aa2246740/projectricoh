"""Reconstruct integer records and score scene colour, film features and quantization."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,ROOT,LOCAL,UNITS,read,dump,sha,predict,arrays
import library as L

ROUTES=('scene_shared_matrix','scene_rgb_matrix','scene_structure','scene_weighted','scene_shared_structure')


def weighted_loss(pred,v,weight=None):
    e=rt.delta_e00(rt.lab_from_codes(np.rint(pred)),rt.lab_from_codes(v['want']))
    return float(np.average(e*e,weights=v['sw'] if weight is None else weight))


def score_group(v,pred):
    pred=np.rint(pred)
    out=rt.score(v['base_new'],pred,v['want'])
    errors=rt.delta_e00(rt.lab_from_codes(pred),rt.lab_from_codes(v['want']))
    masks=L.regions(v['xyz']);sub={}
    for key,mask in masks.items():
        sub[key]=rt.stats(errors[mask])
    high=v['xyz'][:,1]>=.72
    sub['highlights']=rt.stats(errors[high])
    ids=v['photo_id'].astype(int);photos=[]
    for pid in np.unique(ids[ids>=0]):
        use=ids==pid
        den=rt.delta_e00(rt.lab_from_codes(v['base_new'][use]),rt.lab_from_codes(v['want'][use]))
        de=rt.stats(errors[use]);d=float(np.median(den))
        photos.append(dict(photo_id=int(pid),de00=de,baseline_median_de00=d,
            similarity_percent=None if d<.25 else 100*(1-de['median']/d),
            highlight_share=float(high[use].mean())))
    out.update(color_regions=sub,photos=photos,bright_photos=sum(p['highlight_share']>=.1 for p in photos))
    return out


def features(unit,entry,target):
    ui=UNITS.index(unit);camera=rt.Camera(ui)
    white=np.array([.3127/.3290,1.,(1-.3127-.3290)/.3290])
    ev=np.linspace(-10,7,545)
    xyz=.18*2**ev[:,None]*white
    raw=L.raw_from_xyz(camera,xyz,unit);x=C.input_codes(raw,unit)
    desired=target(xyz);continuous=predict(entry,x,ui);actual=np.rint(continuous)
    a,b=rt.lab_from_codes(actual),rt.lab_from_codes(desired)
    de=rt.delta_e00(a,b)
    valid=np.all((x>=0)&(x<=4095)&(raw>=0)&(raw<=4095),axis=1)
    bands={}
    for name,mask in dict(shadow=(ev>=-7)&(ev<=-3),midtone=(ev>=-1)&(ev<=1),highlight=(ev>=1)&(ev<=3)).items():
        bands[name]=dict(de00=rt.stats(de[mask]),target_ab_median=np.median(b[mask,1:],axis=0),
            output_ab_median=np.median(a[mask,1:],axis=0),
            chroma_ab_error_median=float(np.median(np.linalg.norm(a[mask,1:]-b[mask,1:],axis=1))),
            supported_points=int((mask&valid).sum()),
            supported_de00=rt.stats(de[mask&valid]),
            supported_chroma_ab_error_median=float(np.median(np.linalg.norm(a[mask&valid,1:]-b[mask&valid,1:],axis=1))) if (mask&valid).any() else None)
    neutral_window=valid&(ev>=-7)&(ev<=3)
    continuous_lab=rt.lab_from_codes(continuous)
    continuous_L=continuous_lab[neutral_window,0];target_L=b[neutral_window,0]
    gray_shape=dict(eligible_points=int(neutral_window.sum()),
        negative_lightness_steps=int((np.diff(continuous_L)<-.001).sum()),
        maximum_Lstar_drawdown=float((np.maximum.accumulate(continuous_L)-continuous_L).max()) if len(continuous_L) else None,
        target_maximum_Lstar_drawdown=float((np.maximum.accumulate(target_L)-target_L).max()) if len(target_L) else None,
        counts_are_on_supported_scene_neutral_axis=True)
    target_slope=np.gradient(b[:,0],ev);actual_slope=np.gradient(continuous_lab[:,0],ev)
    shoulder=(ev>=0)&(ev<=5)
    slope_error=abs(actual_slope-target_slope)
    tone=dict(bands=bands,gray_shape=gray_shape,EV_axis=ev,target_RGB=desired,prediction_RGB=actual,
        conditioned_input=x,modeled_input_supported=valid,
        last_supported_gray_EV=float(ev[valid].max()) if valid.any() else None,
        shoulder_slope_error_Lstar_per_EV=rt.stats(slope_error[shoulder]),
        shoulder_error_de00=rt.stats(de[shoulder]),
        supported_shoulder_error_de00=rt.stats(de[shoulder&valid]),
        supported_shoulder_slope_error=rt.stats(slope_error[shoulder&valid]),
        target_rolloff_EV=float(ev[(target_slope<1)&(ev>0)][0]) if ((target_slope<1)&(ev>0)).any() else None,
        output_rolloff_EV=float(ev[(actual_slope<1)&(ev>0)][0]) if ((actual_slope<1)&(ev>0)).any() else None,
        input_clipping_is_model_boundary_not_measured_sensor_dynamic_range=True,
        supported_input_requires_RAW_and_conditioned_u12_bounds=True)
    # Equal-luminance saturated hues at several exposures, never used for fitting.
    import colorsys
    colors=np.array([colorsys.hsv_to_rgb(h/360,.85,1) for h in range(0,360,30)])
    from gxr_studio.lut.spaces import matrix
    color_xyz=colors@matrix('rec709').T
    color_xyz/=color_xyz[:,1,None]
    exposures=np.linspace(-4,4,33)
    world=(color_xyz[:,None,:]*(.18*2**exposures)[None,:,None]).reshape(-1,3)
    world_raw=L.raw_from_xyz(camera,world,unit)
    inp=C.input_codes(world_raw,unit)
    desired=target(world);output=np.rint(predict(entry,inp,ui))
    la,lb=rt.lab_from_codes(output),rt.lab_from_codes(desired)
    ca,cb=np.linalg.norm(la[:,1:],axis=1),np.linalg.norm(lb[:,1:],axis=1)
    ha,hb=np.arctan2(la[:,2],la[:,1]),np.arctan2(lb[:,2],lb[:,1])
    defined=(ca>=5)&(cb>=5)
    angle=abs(np.angle(np.exp(1j*(ha-hb))))*180/np.pi
    error=rt.delta_e00(la,lb)
    supported=np.all((inp>=0)&(inp<=4095)&(world_raw>=0)&(world_raw<=4095),axis=1)
    drift=[]
    signed_error=np.angle(np.exp(1j*(ha-hb)))*180/np.pi
    for j in range(12):
        ix=np.arange(j*len(exposures),(j+1)*len(exposures))
        use=ix[defined[ix]&supported[ix]]
        if len(use)<3:continue
        values=np.unwrap(np.deg2rad(signed_error[use]))*180/np.pi
        drift.append(dict(input_hue_degrees=j*30,eligible_EV_points=len(use),
            residual_hue_span_degrees=float(np.ptp(values)),
            residual_after_constant_hue_offset_median_degrees=float(np.median(abs(values-np.median(values))))))
    rows=[]
    for j,e in enumerate(exposures):
        ix=np.arange(12)*len(exposures)+j;use=defined[ix]
        rows.append(dict(EV=float(e),de00=rt.stats(error[ix]),
            hue_error_degrees=rt.stats(angle[ix][use]),
            absolute_chroma_error=rt.stats(abs(ca[ix]-cb[ix])),
            defined_hues=int(use.sum()),
            unsupported_input_hues=int((~supported[ix]).sum())))
    chroma=dict(by_EV=rows,overall_de00=rt.stats(error),hue_error_degrees=rt.stats(angle[defined]),
        supported_input_de00=rt.stats(error[supported]),
        supported_input_hue_error_degrees=rt.stats(angle[defined&supported]),
        total_hue_test_points=len(defined),supported_hue_test_points=int(supported.sum()),
        defined_supported_hue_points=int((defined&supported).sum()),
        supported_input_chroma_error=rt.stats(abs(ca-cb)[supported]),
        supported_relative_chroma_error_percent=rt.stats((100*abs(ca-cb)/np.maximum(cb,5))[defined&supported]),
        brightness_dependent_hue_residual_by_input_hue=drift,
        brightness_dependent_hue_span_degrees=rt.stats(np.asarray([d['residual_hue_span_degrees'] for d in drift])),
        residual_span_is_a_fixed_model_diagnostic_not_a_proven_hardware_lower_bound=True,
        chroma_error=rt.stats(abs(ca-cb)),no_luminance_axis_in_sector_table=True,
        RGB_curves_and_matrix_can_still_create_some_brightness_dependent_hue=True,
        pure_color_sweeps_not_independent_real_photos=True)
    return tone,chroma


def baseline_record(unit,name):
    rows=read(LOCAL/'g157_layouts/release/manifest.json')['records']
    found=next((r for r in rows if r['unit']==unit and r['kind']=='look' and r['name']==name),None)
    if found:return Path(found['record_file']).read_bytes(),dict(kind='frozen_g157_existing_Look',sha256=found['sha256'],name=name)
    entry=rt.Camera(UNITS.index(unit)).entry
    return entry,dict(kind='stock04_reference_not_an_existing_film_Look',sha256=hashlib.sha256(entry).hexdigest())


def analyze(ordinal,unit,phase):
    film=L.CATALOG['films'][ordinal];ui=UNITS.index(unit);root=LOCAL/'films'/f'{ordinal:02d}'/unit
    bank={p.stem:arrays(p) for p in root.glob('*.npz') if p.stem not in ('train_weighted','train_jpeg')}
    train=bank['train'];route_rows={};predictions={};records={};receipts={}
    literal=C.module('film_r2_analysis_literal',C.frozen('research/bluecyan_r1/verify.py')).predict_literal
    for route in ROUTES:
        index=film['indices'][route];base=LOCAL/'fits'/unit/f'{index:02d}'
        if route=='scene_shared_structure' and not (base/'iterate.json').exists():continue
        path=base/('exact.json' if (base/'exact.json').exists() else 'iterate.json')
        doc=read(path);entry=Path(doc['record_file']).read_bytes()
        assert sha(doc['record_file'])==doc['record_sha256'] and doc['nice']==15
        assert entry[1]==(7 if route in ('scene_rgb_matrix','scene_structure','scene_weighted') else 1)
        check=C.codec.record_checks(entry)
        assert check['row_crcs_valid'] and check['existing_row_domain_checks_pass']
        ordinary=bytearray(entry);ordinary[0]=1
        pred={};maxdiff=0.;scores={}
        for group,v in bank.items():
            p=predict(entry,v['x'],ui);ref=literal(C.model(ui),bytes(ordinary),v['x'])
            delta=float(abs(ref-p).max());maxdiff=max(maxdiff,delta);assert delta<1e-8
            mismatches=np.rint(ref)!=np.rint(p)
            if mismatches.any():
                assert np.all(abs((p-np.floor(p))-.5)[mismatches]<1e-10)
            pred[group]=p;scores[group]=score_group(v,p)
        loss=weighted_loss(pred['train'],train)
        focused=np.ones(len(train['x']))
        for mask in L.regions(train['xyz']).values():focused[mask]=2.5
        focus_loss=weighted_loss(pred['train'],train,train['sw']*focused)
        route_rows[route]=dict(route=route,record_file=doc['record_file'],record_sha256=doc['record_sha256'],
            record_bytes=552,flags=entry[1],canonical_slot=entry[0],curve_count=3 if entry[1]&4 else 1,
            fit_phase=doc['phase'],reference_exact_checked=doc['phase']=='exact',
            selected_origin=doc['origin'],retained_unmodified_template=doc['payload_bytes_changed']==0,
            rejected_integer_candidates=len([x for x in doc['checks'] if not x['quality']['passes']]),
            exact_attempts=len(doc['attempts']) if doc['phase']=='exact' else None,
            all_solver_starts_converged=all(a['receipt']['success'] for a in doc['attempts']),
            quality=doc['quality'],unweighted_integer_training_loss=loss,focused_integer_training_loss=focus_loss,
            literal_RGB_maximum_difference=maxdiff,scores=scores,checks=check,
            training_only_record_selection=True)
        records[route]=entry;predictions[route]=pred;receipts[route]=doc
    full_routes=('scene_rgb_matrix','scene_structure','scene_weighted')
    chosen=min(('scene_rgb_matrix','scene_structure'),
        key=lambda r:(route_rows[r]['unweighted_integer_training_loss'],r))
    focused=min(full_routes,key=lambda r:(route_rows[r]['focused_integer_training_loss'],r))
    look_route=min((r for r in ('scene_shared_matrix','scene_shared_structure') if r in route_rows),
        key=lambda r:(route_rows[r]['unweighted_integer_training_loss'],r))
    target=L.FilmTarget(film)
    tone,chroma=features(unit,records[chosen],target)
    old,oldinfo=baseline_record(unit,film['name']);oldpred={g:predict(old,v['x'],ui) for g,v in bank.items()}
    oldscores={g:score_group(v,oldpred[g]) for g,v in bank.items()}
    alternatives={}
    for key in ('want_jpeg','want_scene_srgb_control','want_scene_default_control'):
        v=bank['photo_iso200']
        control=v[key] if key in v else target(v['xyz'],usage='scene_default_control')
        e=rt.delta_e00(rt.lab_from_codes(control),rt.lab_from_codes(v['want']))
        alternatives[key]=dict(target_difference_de00=rt.stats(e),same_fixed_scene_target_used_for_all_candidate_scores=True)
    primary='photo_iso200'
    look=route_rows[look_route]['scores'][primary];full=route_rows[chosen]['scores'][primary]
    gap=None if look['similarity_percent'] is None or full['similarity_percent'] is None else full['similarity_percent']-look['similarity_percent']
    penalty=look['de00']['median']-full['de00']['median']
    provisional=gap is not None and gap<2 and penalty<=.25
    quantum=[]
    if phase=='final':
        # The saved final record is selected only by the integer training objective.
        # Holdout gates admit/reject it; they never select another fitting seed.
        selected=route_rows[chosen]
        assert selected['reference_exact_checked'],'Final selected film record needs full-start exact confirmation'
        meta=read(LOCAL/'targets'/unit/f'{film["indices"][chosen]:02d}/profile.json')
        gate=C.load_assess().Gate(meta,bank,old)
        for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
            for phase_values in itertools.product((0.,.25,.5,.75),repeat=3):
                ph=np.asarray(phase_values)
                a={k:C.ba.phase_output(oldpred[k],ph,order,rt.mm) for k in gate.rows}
                b={k:C.ba.phase_output(predictions[chosen][k],ph,order,rt.mm) for k in gate.rows}
                q=gate.assess(a,b)
                v=bank[primary]
                fp=b[primary]
                lp=C.ba.phase_output(predictions[look_route][primary],ph,order,rt.mm)
                fs=rt.score(v['base_new'],fp,v['want']);ls=rt.score(v['base_new'],lp,v['want'])
                gd=None if fs['similarity_percent'] is None or ls['similarity_percent'] is None else fs['similarity_percent']-ls['similarity_percent']
                pd=ls['de00']['median']-fs['de00']['median']
                bs=rt.score(v['base_new'],a[primary],v['want'])
                overall=(fs['de00']['median']<=bs['de00']['median']+1e-10 and
                         fs['de00']['p95']<=bs['de00']['p95']+.25+1e-10)
                quantum.append(dict(order=order,phase=phase_values,passes=bool(q['passes'] and overall),
                    failures=q['failures']+([] if overall else ['primary_median_p95']),
                    full_similarity_percent=fs['similarity_percent'],Look_similarity_percent=ls['similarity_percent'],
                    full_minus_Look_pp=gd,Look_extra_median_de00=pd,
                    Look_safe=bool(gd is not None and gd<2 and pd<=.25)))
    signature=hashlib.sha256(json.dumps({r:dict(phase=d['fit_phase'],record=d['record_sha256'])
        for r,d in route_rows.items()},sort_keys=True).encode()).hexdigest()
    result=dict(analysis_revision='r3_unweighted_primary_weighted_control',input_fit_signature=signature,
        film=film['name'],ordinal=ordinal,unit=unit,phase=phase,routes=route_rows,
        selected_route=chosen,focused_training_winner=focused,selection_uses_photo_holdout=False,
        primary_selection_rule='Unweighted integer-training winner of black-box and structure methods; weighted method is a separate control',
        selected_Look_route=look_route,Look_structure_control_available='scene_shared_structure' in route_rows,
        Look_reference_exact_checked=route_rows[look_route]['reference_exact_checked'],
        placement_classification_complete='scene_shared_structure' in route_rows and route_rows[look_route]['reference_exact_checked'],
        existing_baseline=oldinfo,existing_baseline_scores=oldscores,
        full_minus_Look_pp=gap,Look_extra_median_de00=penalty,
        training_improved_vs_stock04=route_rows[chosen]['unweighted_integer_training_loss']<weighted_loss(train['base_new'],train)-1e-9,
        primary_photo_improved_vs_baseline=full['de00']['median']<oldscores[primary]['de00']['median']-1e-9,
        provisional_Look_safe=bool(provisional),thresholds=L.CATALOG['rules'],
        film_policy_full_slot=film['family'] not in ('bw','instant'),
        tone=tone,brightness_dependent_color=chroma,control_target_differences=alternatives,
        quantization=quantum,quantization_passes=sum(q['passes'] for q in quantum),quantization_branches=len(quantum),
        quantization_Look_safe_branches=sum(q['Look_safe'] for q in quantum),
        aggregate_field_error_budget_closed=False,actual_candidate_camera_exposures=0)
    out=LOCAL/'analysis'/f'{ordinal:02d}'/unit/(phase+'.json');dump(out,result)
    # Arrays that expose the private gray response stay in local/ as well.
    print('ANALYZED',ordinal,film['name'],unit,phase,'selected',chosen,
        'Look/full',round(look['similarity_percent'],2) if look['similarity_percent'] is not None else None,
        round(full['similarity_percent'],2) if full['similarity_percent'] is not None else None,
        'quant',result['quantization_passes'],'/',len(quantum),flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--film',type=int,required=True)
    p.add_argument('--unit',choices=UNITS,required=True);p.add_argument('--phase',choices=('screen','final'),default='screen')
    args=p.parse_args();analyze(args.film,args.unit,args.phase)


if __name__=='__main__':main()
