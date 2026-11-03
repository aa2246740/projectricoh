"""Read-only final artifact/registry audit; does not recreate task Scratch."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import struct
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capabilities import mount_l1_enabled

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hashes', action='store_true')
    ap.add_argument('--require-clean', action='store_true')
    args = ap.parse_args()
    registry = read(HERE/'candidate_registry.json')
    assert registry['completed_main_profiles']==registry['expected_main_profiles']==105
    profiles = registry['profiles']
    confirmations = read(HERE/'exact_confirmation_summary.json')
    ramp = read(HERE/'mount_ramp_scope_summary.json')
    for name in ('exact_confirmation_summary','solver_provenance','mount_ramp_scope_summary'):
        assert sha(HERE/(name+'.json'))==registry[name+'_sha256']
    assert registry['all_build_candidates_exact_confirmed']
    assert sha(HERE/'local/solver_review_20261103/REVIEW.md')==registry['full_start_review_protocol_sha256']
    pending=read(HERE/'pending_exact_confirmations.json')
    assert sha(HERE/'pending_exact_confirmations.json')==registry['pending_exact_confirmations_sha256']
    assert pending['not_in_DAT_build_list']
    gate_checks=read(HERE/'full_confirmation_gate_checks.json')
    assert sha(HERE/'full_confirmation_gate_checks.json')==registry['full_confirmation_gate_checks_sha256']
    assert gate_checks['status']=='PASS' and gate_checks['valid_perturbed_None_record_rejected']
    assert sha(HERE/gate_checks['detail_file'])==gate_checks['detail_sha256']
    assert sha(HERE/gate_checks['mutated_record_file'])==gate_checks['mutated_record_sha256']
    gate_detail=read(HERE/gate_checks['detail_file'])
    assert gate_detail['positive']['status']=='PASS' and gate_detail['negative']['status']=='REVIEW'
    assert all(p['source']['similarity_percent'] is None for g in gate_detail['negative']['groups'].values() for p in g['photos'])
    assert any(p['exact']['de00'][k]>p['source']['de00'][k]+p['absolute_tolerance'][k]
               for g in gate_detail['negative']['groups'].values() for p in g['photos'] for k in ('median','p95'))
    provenance=read(HERE/'solver_provenance.json')
    assert provenance['actual_solver']=='scipy TRF/SVD' and not provenance['guarded_normal_factorisation_used']
    assert provenance['gate_hashes']['verification.json']==sha(HERE/'verification.json')
    for adapter in provenance['adapters'].values():
        assert not adapter['guarded_normal_factorisation_called'] and not adapter['delivery_1530_gate_accepts_this_flow']
        assert sha(HERE/adapter['adapter_receipt'])==adapter['adapter_receipt_sha256']
        assert sha(HERE/adapter['local_equation_record_gate'])==adapter['local_equation_record_gate_sha256']
    assert not registry['MOUNT_continuous_full_colour_accepted_intervals']
    assert ramp['profiles_complete']==35 and not ramp['verified_continuous_full_colour_intervals']
    assert not ramp['global_amplitude_or_chroma_update_applied']
    ramp_records={r['index']:r for r in ramp['profiles']}
    ramp_points=read(HERE/ramp['private_sample_points'])
    points=ramp_points['all_formal_points']
    assert len(points)==312 and ramp_points['no_continuous_range_accepted']
    for evidence in ramp['sampled_control_evidence']:
        values=sorted(p['raw_input'] for p in points if p['channel']==evidence['channel']
                      and p['gray'] and not p['excluded'] and p['q_nominal']>.2)
        assert values==ramp_points['active_grey_sample_RAW_WB'][evidence['channel']]
        assert len(values)==evidence['active_grey_points']
        assert min(values)==evidence['RAW_WB_min'] and max(values)==evidence['RAW_WB_max']
        unique=sorted(set(values))
        assert max(b-a for a,b in zip(unique,unique[1:]))==evidence['largest_RAW_WB_gap_between_active_samples']
        assert not evidence['continuous_full_colour_accepted_intervals']
    skin=[p for p in points if p['channel']=='R' and p['patch']=='skin']
    assert len(skin)==ramp['skin_R_points']
    assert sum(p['observed_ycc'][1]*p['predicted_ycc'][1]<0 for p in skin)==ramp['skin_R_Cb_opposite_sign_points']
    expected = {(u,i) for u in ('mount-a12','a12-50','a12-28') for i in range(35)}
    assert len(profiles)==105 and {(r['unit'],r['index']) for r in profiles}==expected
    verification = read(HERE/'verification.json')
    assert verification['status']=='PASS' and verification['full_recipe_matrix_complete']
    verified = {(r['file'],r['record_sha256']) for r in verification['records']}
    assert sha(HERE/'verification.json')==registry['verification_sha256']
    chroma = read(HERE/'mount_chroma_calibration_summary.json')
    quantum = read(HERE/'mount_quantization_sensitivity_summary.json')
    assert sha(HERE/'mount_chroma_calibration_summary.json')==registry['mount_chroma_calibration_summary_sha256']
    assert sha(HERE/'mount_quantization_sensitivity_summary.json')==registry['mount_quantization_sensitivity_summary_sha256']
    assert not chroma['main_model_updated'] and not chroma['global_RGB_curve_gain_applied']
    assert quantum['profiles_complete']==35 and quantum['branches_per_group']==128
    quantum_records = {r['index']:r for r in quantum['profiles']}
    for model in chroma['models']:
        assert sha(HERE/model['file'])==model['sha256']
        data = read(HERE/model['file'])
        matrix = data['chroma_differential_matrix']
        expected = []
        for point,x in zip(data['active_points'],data['predicted_components']):
            fitted = [x[0],x[1]*matrix[0][0]+x[2]*matrix[1][0],x[1]*matrix[0][1]+x[2]*matrix[1][1]]
            expected.append([a-b for a,b in zip(fitted,point['native_ycc_delta'])])
        assert all(abs(a-b)<1e-12 for row,saved in zip(expected,data['component_residuals']) for a,b in zip(row,saved))
        for evaluation in (r for r in chroma['evaluations'] if r['model_id']==data['model_id']):
            positions = [i for i,p in enumerate(data['active_points']) if p['session']==evaluation['evaluation_scope']]
            rms = [math.sqrt(sum(expected[i][c]**2 for i in positions)/len(positions)) for c in range(3)]
            assert max(abs(a-b) for a,b in zip(rms,evaluation['calibrated_component_rmse']))<1e-12
    for row in quantum['profiles']:
        assert sha(HERE/row['private_detail'])==row['private_detail_sha256']
        detail = read(HERE/row['private_detail'])
        assert detail['record_sha256']==row['record_sha256']
        for values in detail['groups'].values():
            assert len(values['branches'])==128
            assert sha(HERE/values['point_envelope_file'])==values['point_envelope_sha256']
    selected_records = {(row['unit'],row['index']):row['record_sha256'] for row in profiles}
    photo_path = HERE/'photo_scores.csv'
    assert sha(photo_path)==verification['photo_scores_sha256']
    with photo_path.open(newline='') as stream:
        photos = list(csv.DictReader(stream))
    assert len(photos)==verification['selected_main_photo_scores']
    photo_points = {}
    for photo in photos:
        key = photo['unit'], int(photo['index'])
        assert photo['record_sha256']==selected_records[key], ('Photo evidence uses another record',key)
        assert photo['used_to_select_parameters']=='False' and photo['label']=='电脑预测'
        group = (*key,photo['group'])
        photo_points[group] = photo_points.get(group,0)+int(photo['points'])
    assert {key[:2] for key in photo_points}=={(u,i) for u in ('mount-a12','a12-50') for i in range(35)}
    for row in profiles:
        assert (row['fit_receipt'],row['record_sha256']) in verified
        path = (HERE/row['record_file']).resolve()
        assert path.is_relative_to(HERE/'local')
        entry = path.read_bytes()
        assert len(entry)==552 and sha(path)==row['record_sha256']
        fit = read(HERE/row['fit_receipt'])
        for group,score in fit['scores'].items():
            if group.startswith('photo_') and score:
                assert photo_points[row['unit'],row['index'],group]==score['candidate']['de00']['n']
        original = HERE/row['selected_fit_record']
        assert original.read_bytes()==entry and fit['record']['sha256']==row['record_sha256']
        assert row['quality']['passes'] and row['quality']['new_reverse_hue_intervals']==0
        assert row['quality']['max_integer_gradient_step_de00']<=2
        assert row['verified_record_replay'] and row['S_mode']=='04 Standard'
        if row['index']==30:
            target = read(HERE/'local/targets'/row['unit']/'30.json')
            assert entry==bytes.fromhex(target['template_hex'])
        if row['unit']=='mount-a12':
            assert mount_l1_enabled() and row['main_level']==1
            assert row['new7_raw_holdout_replayed']
            assert row['new7_raw_holdout']['record_sha256']==row['record_sha256']
            assert row['mount_L1_domain']['record_sha256']==row['record_sha256']
            assert not row['mount_L1_domain']['full_curve_amplitude_calibrated']
            assert row['mount_output_quantization_sensitivity']==quantum_records[row['index']]
            assert quantum_records[row['index']]['record_sha256']==row['record_sha256']
            assert row['mount_ramp_sample_scope']==ramp_records[row['index']]
            assert ramp_records[row['index']]['record_sha256']==row['record_sha256']
            assert not ramp_records[row['index']]['quantitatively_accepted_continuous_intervals']
        if row['recommendation'] in ('replace_candidate','add_candidate'):
            proof=row['exact_confirmation']
            assert proof in confirmations['profiles']
            assert row['exact_confirmation_certified_record_sha256']==row['record_sha256']
            assert sha(HERE/proof['source_fit'])==proof['source_fit_sha256']
            assert sha(HERE/proof['exact_fit'])==proof['exact_fit_sha256']
            exact=read(HERE/proof['exact_fit'])
            assert exact['backend']=='fast' and exact['full_start_confirmation']
            assert exact['all_original_starts_axes_and_feasible_candidates']
            assert exact['final_saved_decoded_record_and_fixtures_rebuilt']
            assert exact['reviewed_holdout_gate']['status']=='PASS'
            assert sha(HERE/proof['start_manifest'])==proof['start_manifest_sha256']
            starts=read(HERE/proof['start_manifest'])
            assert len(starts['starts'])==len(exact['solver_attempts'])==proof['exact_confirmation_solver_attempts']
            assert starts['original_declared_current_and_gray_starts'] and starts['all_feasible_integer_candidates']
            assert starts['fast_candidate_extra_start_and_kept']
            assert any('current_row' in r['start_names'] for r in starts['starts'])
            assert any('fast_candidate_extra_integer' in r['start_names'] for r in starts['starts'])
            for item in starts['starts']:
                vector=item['vector']
                assert hashlib.sha256(struct.pack('<'+'d'*len(vector),*vector)).hexdigest()==item['vector_sha256']
            for item in starts['feasible_inputs']:
                assert sha(HERE/item['file'])==item['sha256']
            assert proof['exact_objective']<=proof['source_objective']+proof['reference_reduction_noise']['tolerance']
            assert proof['target_sha256']==fit['target_sha256']
            assert (proof['exact_fit'],proof['exact_record_sha256']) in verified
            assert row['record_sha256'] in (proof['source_record_sha256'],proof['exact_record_sha256']) or (
                fit.get('canonical_equivalence_parent')==proof['exact_fit'] and row['exact_confirmation_via_canonical_equivalence'])
            assert not row['scene_regression_review']
            assert fit['recommend_next_dat_build'] and not fit['mount_probe_pending']
            if row['unit']=='mount-a12':
                assert row['new7_raw_holdout']['scene_gate_pass']
    lists = read(HERE/'dat_candidate_lists.json')
    assert lists['candidate_registry_sha256']==sha(HERE/'candidate_registry.json')
    accepted = {(r['unit'],r['index'],r['record_sha256']) for r in profiles
                if r['recommendation'] in ('replace_candidate','add_candidate')}
    listed = {(u,r['index'],r['record_sha256']) for u,items in lists['units'].items() for r in items['accepted']}
    assert listed==accepted
    assert {(r['unit'],r['index']) for r in pending['profiles']}=={
        (r['unit'],r['index']) for r in profiles if r['recommendation'] in ('pending_full_start_exact','review_exact_holdout')}
    assert all(r['backend']=='exact_TRF_SVD' and not r['delivery_1530_gate_accepts_this_complete_flow'] for r in profiles)
    for unit,items in lists['units'].items():
        partitions = [items['accepted'],items['not_replaced'],items['not_added']]
        assert sum(map(len,partitions))==35
        assert {r['index'] for group in partitions for r in group}==set(range(35))
    for row in registry['mount_L0_reference_build_candidates']:
        assert (row['fit_receipt'],row['record_sha256']) in verified
        path = (HERE/row['record_file']).resolve()
        assert path.is_relative_to(HERE/'local')
        assert len(path.read_bytes())==552 and sha(path)==row['record_sha256']
    relative = sorted(str(p.relative_to(ROOT)) for p in (HERE/'local').rglob('*') if p.is_file())
    result = subprocess.run(['git','-C',str(ROOT),'check-ignore','-z','-v','--stdin'],
                            input=('\0'.join(relative)+'\0').encode(), capture_output=True, check=True)
    fields = result.stdout.decode().split('\0')
    assert fields[-1]=='' and (len(fields)-1)%4==0
    ignored = set(fields[3:-1:4])
    assert set(relative)<=ignored
    hashed = 0
    if args.hashes:
        for line in (HERE/'SHA256SUMS').read_text().splitlines():
            expected_hash,name = line.split('  ',1)
            path = (HERE/name).resolve()
            assert path.is_relative_to(HERE) and sha(path)==expected_hash, name
            hashed += 1
    if args.require_clean:
        cleanup = read(HERE/'cleanup.json')
        assert cleanup['removed'] and not Path(cleanup['task_scratch']).exists()
        assert read(HERE/'seal_receipt.json')['full_main_matrix_complete']
    print(json.dumps(dict(status='PASS', main_profiles=105, dat_build_candidates=len(accepted),
        records_exact=105, independently_replayed=True, ignored_local_files=len(relative),
        photo_evidence_record_sha_matches=True, photo_rows_checked=len(photos),
        mount_quantization_records_checked=35, local_chroma_models_checked=len(chroma['models']),
        exact_confirmed_build_candidates=len(accepted), mount_discrete_ramp_records_checked=35,
        hashes_checked=hashed, scratch_absent=not Path('/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-redo-r1').exists(),
        candidate_registry_sha256=sha(HERE/'candidate_registry.json'),
        report_sha256=sha(HERE/'REPORT.md')),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
