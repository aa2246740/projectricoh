"""Read-only artifact audit for the g155c-compatible round, including its seal."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import g155c_baseline as baseline

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(hashes,clean):
    registry=read(HERE/'candidate_registry.json');lists=read(HERE/'dat_candidate_lists.json')
    state=read(HERE/'local/round2_state.json');D=baseline.decoder()
    assert lists['candidate_registry_sha256']==sha(HERE/'candidate_registry.json')
    assert registry['published_looks_per_unit']==10 and registry['completed_main_profiles']==105
    assert len(registry['profiles'])==105 and len({(r['unit'],r['index']) for r in registry['profiles']})==105
    assert registry['pending_exact_confirmations_sha256']==sha(HERE/'pending_exact_confirmations.json')
    assert registry['compatible_look_candidates_sha256']==sha(HERE/'compatible_look_candidates.json')
    assert registry['row_budget_sha256']==sha(HERE/'g155c_row_budget.json')
    manifest=read(HERE/'local/g155c_baseline/manifest.json')
    for p in manifest['profiles']:assert sha(ROOT/p['source'])==p['sha256']
    accepted=[];replacements={};snapshots=set()
    for row in registry['profiles']:
        key=row['unit'],row['index'];ui=baseline.UNITS.index(row['unit'])
        record=HERE/row['record_file'];content=record.read_bytes()
        assert len(content)==552 and sha(record)==row['record_sha256']
        assert row['flags']==content[1] and row['base05_flags']==1
        replay=read(HERE/row['scores_receipt'])
        assert sha(HERE/row['scores_receipt'])==row['scores_receipt_sha256']
        assert replay['record_sha256']==row['record_sha256']
        source=HERE/row['fit_receipt'];assert sha(source)==row['fit_sha256']
        doc=read(source)
        for snapshot in (doc.get('code_snapshot'),doc.get('postprocess_code_snapshot')):
            if not snapshot or snapshot['folder'] in snapshots:continue
            for name,digest in snapshot['files'].items():assert sha(HERE/snapshot['folder']/name)==digest
            snapshots.add(snapshot['folder'])
        base=next((r for r in baseline.records()[row['unit']] if r['name']==row['name'] and r['kind']==row['kind']),None)
        assert row['published']==(base is not None)
        if base:
            assert row['current_record_sha256']==base['record_sha256']
        else:
            assert row['comparison_baseline_kind']=='g155c_base05_offline_reference'
            assert not row['accepted_for_existing_g155c_slot']
        if row['index']==30:
            assert base is not None and content==(HERE/base['record_file']).read_bytes()
        if row['accepted_for_existing_g155c_slot']:
            assert base and row['recommendation']=='replace_candidate' and row['flags_compatible']
            assert replay['accepted'] and row['quality']['passes'] and row['quality']['new_reverse_hue_intervals']==0
            assert not row['scene_regression_review'] and row['full_exact_confirmation_status']=='PASS'
            if row.get('builtin_slot')==5:assert content[1]==1
            if row['kind']=='look':
                slot=content[0]
                parent=next(r for r in registry['profiles'] if r['unit']==row['unit'] and r.get('builtin_slot')==slot)
                actual=parent['flags'] if parent['accepted_for_existing_g155c_slot'] else next(
                    r for r in baseline.records()[row['unit']] if r['kind']=='builtin' and r['slot']==slot)['flags']
                assert row['look_base_slot']==slot and content[1]==row['required_base_flags']==actual
                if row.get('requires_companion_builtin'):
                    assert parent['accepted_for_existing_g155c_slot'] and parent['record_sha256']==row['requires_companion_builtin']['record_sha256']
            if row['kind']=='look':assert D.content_crc(content,1<<ui)==struct.unpack_from('>I',content,4)[0]
            proof=row['exact_confirmation'];fit=read(HERE/proof['exact_fit'])
            assert sha(HERE/proof['exact_fit'])==proof['exact_fit_sha256']
            assert proof['full_start_confirmation'] and proof['status']=='PASS'
            assert fit['all_original_starts_axes_and_feasible_candidates']
            assert fit['final_saved_decoded_record_and_fixtures_rebuilt']
            assert sha(HERE/proof['start_manifest'])==proof['start_manifest_sha256']
            assert len(read(HERE/proof['start_manifest'])['starts'])==proof['exact_confirmation_solver_attempts']
            assert row['record_sha256']==proof['exact_record_sha256'] or doc.get('canonical_equivalence_parent')==proof['exact_fit']
            accepted.append(row);replacements[row['unit'],row['name']]=record
        items=lists['units'][row['unit']]['accepted']
        match=[r for r in items if r['index']==row['index']]
        assert bool(match)==row['accepted_for_existing_g155c_slot']
        if match:assert match[0]['record_sha256']==row['record_sha256'] and match[0]['record_file']==row['record_file']
        if row['unit']=='a12-28':assert row['holdout_kind']=='synthetic_only' and not row['photo_holdout_available']
    variants=read(HERE/'compatible_look_candidates.json')['profiles']
    assert len(variants)==30 and len({(v['unit'],v['index'],v['compat_family']) for v in variants})==30
    for v in variants:
        assert sha(HERE/v['record_file'])==v['record_sha256'] and v['flags']==1
        assert v['full_exact_confirmation_status'] in ('PASS','REVIEW')
        if v['compat_family']!='free':assert v['unique_row_cost']['new_unique_rows']<=1
        proof=v['exact_confirmation'];assert proof and sha(HERE/proof['exact_fit'])==proof['exact_fit_sha256']
    costs=baseline.table_cost(replacements)
    assert costs==read(HERE/'g155c_row_budget.json')['selected_existing_slot_replacements']
    assert costs==lists['capacity_prediction']
    for key,row in state['frozen_build38'].items():assert sha(HERE/row['record_file'])==row['record_sha256']
    plan=read(HERE/'local/confirmations/full_exact_28_lens_r5/plan.json')['profiles'];assert len(plan)==32
    for row in plan:
        path=HERE/'local/fits/a12-28'/f'{row["index"]:02d}'/f'L1_full_exact_28_lens_r5_{row["index"]:02d}.json'
        fit=read(path);assert fit['full_start_confirmation'] and fit['all_original_starts_axes_and_feasible_candidates']
        assert fit['exact_confirmation_of']==row['source'] and sha(HERE/row['source'])==row['source_sha256']
    if clean:
        scratch=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/recipe-redo-r1')
        assert not scratch.exists() and read(HERE/'cleanup.json')['removed']
    count=0
    if hashes:
        for line in (HERE/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split('  ',1);path=(HERE/name).resolve()
            assert path.is_relative_to(HERE) and sha(path)==digest,('SHA mismatch',name)
            count+=1
    print(json.dumps(dict(status='PASS',profiles=105,compatible_variants=30,
        full_start_28_confirmations=32,accepted_existing_slots=len(accepted),
        accepted_by_unit=dict(collections.Counter(r['unit'] for r in accepted)),
        frozen_build38_preserved=True,hashes_verified=count,scratch_clean=clean,
        no_DAT_built=True,scope='Record, computer prediction receipts and static capacity only'),ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--hashes',action='store_true');ap.add_argument('--require-clean',action='store_true')
    args=ap.parse_args();main(args.hashes,args.require_clean)
