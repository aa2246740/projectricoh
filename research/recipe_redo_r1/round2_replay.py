"""Rebase saved candidates onto the actual published records, without refitting."""
import argparse
import copy
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import fit_one as fit
from entry_codec import predict,record_checks,encode,look_identity_valid
from g155c_baseline import records,UNITS
from report import select

PRIOR=rt.HERE/rt.read(rt.LOCAL/'round2_state.json')['checkpoint']/'candidate_registry.json'
PRIOR_ROWS={(r['unit'],r['index']):r for r in rt.read(PRIOR)['profiles']}
PRIORITY={'a12-50':(20,21,22,24,26),'mount-a12':(20,22,23,24,26)}
FAMILIES=('free','reuse_tone_matrix','reuse_hue_matrix')


def exact_proof(source,doc):
    if doc.get('full_start_confirmation'):
        proof_path=source
    elif doc.get('canonical_equivalence_parent'):
        proof_path=rt.HERE/doc['canonical_equivalence_parent']
        if not rt.read(proof_path).get('full_start_confirmation'):proof_path=None
    else:proof_path=None
    if proof_path is None:
        paths=source.parent.glob('L[01]_*.json')
        possible=[(p,rt.read(p)) for p in paths]
        possible=[(p,d) for p,d in possible if d.get('full_start_confirmation') and
            d['record']['sha256']==doc['record']['sha256']]
        if possible:proof_path=min(possible,key=lambda p:(p[1]['objective'],str(p[0])))[0]
    if proof_path is None:return None
    proof=rt.read(proof_path)
    manifest=rt.HERE/proof['start_manifest']
    assert rt.sha(manifest)==proof['start_manifest_sha256']
    assert len(rt.read(manifest)['starts'])==len(proof['solver_attempts'])
    assert proof['objective']<=proof['confirmation_source_objective']+proof['reference_reduction_noise']['tolerance']
    return dict(exact_fit=str(proof_path.relative_to(rt.HERE)),exact_fit_sha256=rt.sha(proof_path),
        exact_record_sha256=proof['record']['sha256'],source_fit=proof['exact_confirmation_of'],
        source_record_sha256=proof['confirmation_source_record_sha256'],
        source_objective=proof['confirmation_source_objective'],exact_objective=proof['objective'],
        start_manifest=proof['start_manifest'],start_manifest_sha256=proof['start_manifest_sha256'],
        exact_confirmation_solver_attempts=len(proof['solver_attempts']),
        status=proof['reviewed_holdout_gate']['status'],full_start_confirmation=True,
        source_scores=proof['confirmation_source_scores'],exact_scores=proof['scores'],
        actual_solver_branches=proof['actual_solver_branches'],
        reference_reduction_noise=proof['reference_reduction_noise'])


def source_for(unit,index):
    if index in PRIORITY.get(unit,()):
        compact=[]
        for family in FAMILIES[1:]:
            path=rt.LOCAL/'compat_g155c'/family/'fits'/unit/f'{index:02d}'/'L0_compat_full_exact_r1.json'
            doc=rt.read(path);assert doc['full_start_confirmation']
            compact.append((path,doc))
        return min(compact,key=lambda p:(p[1]['objective'],str(p[0])))
    if unit=='a12-28' or (unit=='mount-a12' and index in (0,1)):
        return select((rt.LOCAL/'fits'/unit/f'{index:02d}').glob('L1_*.json'))
    path=rt.HERE/PRIOR_ROWS[unit,index]['fit_receipt']
    return path,rt.read(path)


def baseline_for(unit,index,catalog):
    target=catalog[index]
    row=next((r for r in records()[unit] if r['name']==target['name'] and r['kind']==target['kind']),None)
    published=row is not None
    if row is None:row=next(r for r in records()[unit] if r['kind']=='builtin' and r['slot']==5)
    return row,published


def score_record(unit,index,path,doc,baseline,catalog):
    ui=UNITS.index(unit);entry=path.with_suffix('.record552').read_bytes()
    checks=record_checks(entry);assert checks['sha256']==doc['record']['sha256']
    assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
    current=(rt.HERE/baseline['record_file']).read_bytes()
    target_root=rt.HERE/doc.get('model_context','local')/'targets'/unit
    meta_path=target_root/f'{index:02d}.json';meta=rt.read(meta_path)
    assert rt.sha(meta_path)==doc['target_sha256']
    family=doc.get('compat_family')
    if not family:
        template=bytes.fromhex(meta['template_hex'])
        if doc.get('parameters'):
            rebuilt=encode(template,doc['parameters'],level=doc.get('record_encoding_level',doc['level']),
                gray=doc.get('gray',False),mirror_iso100=doc.get('mirror_iso100_curve',False),
                look_unit_mask=doc.get('look_unit_mask'))
            assert rebuilt==entry
        else:assert template==entry
    else:
        verification=rt.read(rt.LOCAL/'compat_g155c'/family/'verification.json')
        assert any(v['fit']==str(path.relative_to(rt.HERE)) and v['record_sha256']==checks['sha256'] for v in verification['records'])
    camera=rt.Camera(ui);gradients,rings=fit.quality.fixtures(camera)
    quality=fit.guard(camera,entry,current,gradients,rings,ui,doc.get('gray',False))
    info=rt.read(rt.LOCAL/'inputs'/unit/'photos.json')
    scores={};scenes={};photographs={};groups={}
    for group in meta['input_file_sha256']:
        group_path=target_root/f'{index:02d}_{group}.npz'
        if not group_path.exists():
            assert unit=='a12-28' and group.startswith('photo_'),'Missing required target data'
            scores[group]=None
            continue
        data=rt.arrays(group_path)
        if not len(data['x']):scores[group]=None;continue
        original=rt.arrays(rt.LOCAL/'targets'/unit/f'{index:02d}_{group}.npz')
        assert all(np.array_equal(data[k],original[k]) for k in ('x','want','base'))
        groups[group]=data
        prediction=predict(entry,data['x'],ui);before=predict(current,data['x'],ui)
        saved=rt.arrays(path.with_name(path.stem+'_'+group+'.npz'))['prediction']
        assert np.array_equal(prediction,saved)
        scores[group]=dict(candidate=rt.score(data['base'],prediction,data['want']),
            current=rt.score(data['base'],before,data['want']))
        scores[group]['candidate']['weighted_de00_square']=fit.objective(prediction,data['want'],data['sw'])
        scores[group]['current']['weighted_de00_square']=fit.objective(before,data['want'],data['sw'])
        assert abs(scores[group]['candidate']['de00']['median']-doc['scores'][group]['candidate']['de00']['median'])<1e-10
        if group=='train':assert abs(scores[group]['candidate']['weighted_de00_square']-doc['objective'])<1e-10
        if group.startswith('photo_'):
            scene_names=np.array([info[int(i)]['scene_group'] for i in data['photo_id']])
            scenes[group]={}
            for scene in sorted(set(scene_names)):
                use=scene_names==scene
                scenes[group][scene]=dict(candidate=rt.score(data['base'][use],prediction[use],data['want'][use]),
                    current=rt.score(data['base'][use],before[use],data['want'][use]))
            photographs[group]=[]
            for ident in sorted(set(map(int,data['photo_id']))):
                use=data['photo_id']==ident
                photographs[group].append(dict(photo_id=ident,
                    candidate=rt.score(data['base'][use],prediction[use],data['want'][use]),
                    current=rt.score(data['base'][use],before[use],data['want'][use])))
    new7=None
    if unit=='mount-a12':
        bank=rt.read(rt.HERE/'new7_raw_holdout_summary_L1.json')['artifact_root']
        data=rt.arrays(rt.HERE/bank/f'{index:02d}.npz')
        prediction=predict(entry,data['x'],ui);before=predict(current,data['x'],ui)
        a,b=rt.score(data['base'],prediction,data['want']),rt.score(data['base'],before,data['want'])
        new7=dict(label='电脑预测，机主确认原厂04的七张RAW整组留出',candidate=a,current=b,
            scene_gate_pass=all(a['de00'][k]<=b['de00'][k]+1e-10 for k in ('median','p95')),
            record_sha256=checks['sha256'],RAW_target_file=str((rt.HERE/bank/f'{index:02d}.npz').relative_to(rt.HERE)),
            observed_JPG_used_for_recipe_target=False,calibration_coefficients_not_refitted=True)
        scores['photo_new7_RAW_diagnostic']=dict(candidate=a,current=b)
        photographs['photo_new7_RAW_diagnostic']=[]
        for ident in sorted(set(map(int,data['photo_id']))):
            use=data['photo_id']==ident
            photographs['photo_new7_RAW_diagnostic'].append(dict(photo_id=ident,
                candidate=rt.score(data['base'][use],prediction[use],data['want'][use]),
                current=rt.score(data['base'][use],before[use],data['want'][use])))
    scene_failures=[scene for scene,value in scenes.get('photo_iso200',{}).items()
        if any(value['candidate']['de00'][k]>value['current']['de00'][k]+1e-10 for k in ('median','p95'))]
    if new7 and not new7['scene_gate_pass']:scene_failures.append('mount_natural_20261103_whole_collection')
    primary='synthetic' if ui==1 else 'photo_iso200'
    a,b=scores[primary]['candidate'],scores[primary]['current']
    basic=bool(doc['origin']=='refit' and quality['passes'] and
        a['de00']['median']<b['de00']['median']-1e-9 and a['de00']['p95']<=b['de00']['p95']+.25)
    proof=exact_proof(path,doc)
    exact_ok=proof is not None and proof['status']=='PASS'
    target=catalog[index]
    flags_compatible=entry[1]==1 if target['kind']=='look' or target.get('builtin_slot')==5 else True
    accepted=basic and not scene_failures and exact_ok and flags_compatible
    return dict(label='电脑预测，仅合成' if ui==1 else '电脑预测',unit=unit,index=index,name=doc['name'],
        fit_receipt=str(path.relative_to(rt.HERE)),fit_sha256=rt.sha(path),record_file=str(path.with_suffix('.record552').relative_to(rt.HERE)),
        record_sha256=checks['sha256'],record_bytes=552,flags=entry[1],base05_flags=1,
        flags_compatible=flags_compatible,compat_family=family,quality=quality,scores=scores,
        look_base_slot=int(entry[0]) if target['kind']=='look' else None,
        per_scene=scenes,per_photo=photographs,scene_regression_review=scene_failures,new7_raw_holdout=new7,
        exact_confirmation=proof,full_exact_confirmation_status=proof['status'] if proof else 'PENDING',
        primary_score_group=primary,training_objective=doc['objective'],
        training_improved_over_g155c_reference=doc['objective']<scores['train']['current']['weighted_de00_square']-1e-9,
        gain_over_current_pp={g:None if not v or v['candidate']['similarity_percent'] is None or v['current']['similarity_percent'] is None
            else v['candidate']['similarity_percent']-v['current']['similarity_percent'] for g,v in scores.items()},
        basic_quality_recommendation=basic,candidate_passes_model_gates=basic and not scene_failures and exact_ok,
        accepted=accepted,verified_record_replay=True,
        baseline=baseline,target_sha256=doc['target_sha256'],target_file=str(meta_path.relative_to(rt.HERE)),
        historical_fit_comparison_preserved=True,actual_solver_branches=doc.get('actual_solver_branches',[]),
        all_552_bytes_rebuilt=True,all_scores_recomputed=True,no_DAT_built=True)


def main(unit):
    catalog={r['index']:r for r in rt.read(rt.HERE/'target_catalog.json')['definitions']}
    result=[]
    for index in range(35):
        source,doc=source_for(unit,index);baseline,published=baseline_for(unit,index,catalog)
        replay=score_record(unit,index,source,doc,baseline,catalog)
        replay.update(published=published,comparison_baseline_kind='g155c_published_record' if published else 'g155c_base05_offline_reference',
            kind=catalog[index]['kind'],builtin_slot=catalog[index].get('builtin_slot'),
            deployment_policy='one_new_row' if index in PRIORITY.get(unit,()) else 'prior_model_training_selection')
        variants=[]
        if index in PRIORITY.get(unit,()):
            for family in FAMILIES:
                path=rt.LOCAL/'compat_g155c'/family/'fits'/unit/f'{index:02d}'/'L0_compat_full_exact_r1.json'
                candidate=rt.read(path)
                variants.append(score_record(unit,index,path,candidate,baseline,catalog))
            replay['compatible_variants']=variants
        rt.dump(rt.LOCAL/'round2_replay'/unit/f'{index:02d}.json',replay)
        result.append(dict(index=index,name=doc['name'],accepted=replay['accepted'],record_sha256=replay['record_sha256']))
        print('G155C REPLAY',unit,index,'accepted',replay['accepted'],'flags',replay['flags'],flush=True)
    # The on-disk format checks the descriptor selected by the Look's byte0.
    # Colour Looks reference05. Tri-X references03 and may accompany an
    # admitted independent-curve03 without changing either original record.
    completed=[rt.read(rt.LOCAL/'round2_replay'/unit/f'{i:02d}.json') for i in range(35)]
    builtins={d['builtin_slot']:d for d in completed if d['kind']=='builtin'}
    for data in completed:
        if data['kind']!='look':continue
        slot=data['look_base_slot'];parent=builtins[slot]
        original=next(r for r in records()[unit] if r['kind']=='builtin' and r['slot']==slot)
        required=parent['flags'] if parent['accepted'] and parent['published'] else original['flags']
        data['required_base_flags']=required
        data['flags_compatible']=data['flags']==required
        data['accepted']=bool(data['candidate_passes_model_gates'] and data['flags_compatible'])
        if required!=original['flags']:
            data['requires_companion_builtin']=dict(unit=unit,index=parent['index'],name=parent['name'],
                builtin_slot=slot,record_sha256=parent['record_sha256'],all_or_keep_g155c=True)
        rt.dump(rt.LOCAL/'round2_replay'/unit/f'{data["index"]:02d}.json',data)
    result=[dict(index=d['index'],name=d['name'],accepted=d['accepted'],record_sha256=d['record_sha256']) for d in completed]
    rt.dump(rt.LOCAL/'round2_replay'/unit/'receipt.json',dict(status='PASS',profiles=result,count=35,
        prior_registry_sha256=rt.sha(PRIOR),no_DAT_built=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--unit',required=True,choices=UNITS)
    main(ap.parse_args().unit)
