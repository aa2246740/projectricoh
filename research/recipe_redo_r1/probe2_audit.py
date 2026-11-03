"""Read-only audit of conditional refinements and the static capacity profile."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import g155c_baseline as base

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/probe2_local_response'
CRC_FIELDS=((20,62,8),(82,33,12),(115,96,16),(216,56,212),(284,62,272),
    (346,33,276),(379,66,280),(456,62,448),(518,33,452))


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(photos):
    registry=read(HERE/'candidate_registry.json');summary=read(HERE/'probe2_refit_registry.json')
    assert registry['probe2_refit_registry_sha256']==sha(HERE/'probe2_refit_registry.json')
    assert registry['probe2_response_incorporated'] and not registry['probe2_applied_to_main_admission_model']
    assert summary['total_profiles']==35 and summary['refinement_flows']==27 and summary['retained_shared_or_native']==8
    assert len(summary['profiles'])==35 and len({r['index'] for r in summary['profiles']})==35
    for p in summary['profiles']:
        assert sha(HERE/p['record_file'])==p['record_sha256']
        assert sha(HERE/p['fit_receipt'])==p['fit_sha256']
        data=(HERE/p['record_file']).read_bytes();anchor=(HERE/p['anchor_file']).read_bytes()
        assert len(data)==552 and data[1]==p['flags']
        assert all(struct.unpack_from('>I',data,crc)[0]==zlib.crc32(data[offset:offset+n])&0xffffffff for offset,n,crc in CRC_FIELDS)
        assert p['calibration_sha256']==sha(OUT/'calibration.json') and p['policy_sha256']==sha(OUT/'policy.json')
        if p['retained_shared_or_native']:assert data==anchor
        else:
            allowed={i for offset in (82,379,412,518) for i in (offset+8,offset+16,offset+19)}
            allowed.update(i for _,_,crc in CRC_FIELDS for i in range(crc,crc+4))
            if p['index']<27:allowed.update(range(4,8))
            assert all(i in allowed or a==b for i,(a,b) in enumerate(zip(data,anchor)))
            for offset in (82,379,412):
                for node in (8,16,19):
                    step=data[offset+node]-anchor[offset+node]
                    assert (0<=step<=2) if node in (8,19) else (-2<=step<=0)
            assert sha(HERE/p['verification_receipt'])==p['verification_sha256']
            assert read(HERE/p['verification_receipt'])['status']=='PASS'
            assert sha(HERE/p['start_manifest'])==p['start_manifest_sha256']
            proof=read(HERE/p['fit_receipt']);assert proof['full_start_confirmation']
            assert proof['record_model_max_difference']<1e-7
            if p['index'] in (0,1):assert p['full_exact_confirmation_status']=='REVIEW'
        assert not p['accepted_into_main_DAT_list'] and p['model_error_not_removed']
    prior=read(HERE/'local/checkpoint_shared_priority_20261103T1326/candidate_registry.json')
    assert {(r['unit'],r['index']):r['record_sha256'] for r in registry['profiles']}=={
        (r['unit'],r['index']):r['record_sha256'] for r in prior['profiles']}
    source=read(OUT/'source_manifest.json')
    for row in source['files']:
        assert sha(HERE/row['file'])==row['sha256'] and sha(ROOT/row['source'])==row['sha256']
    if photos:
        for row in source['photo_inputs']:assert sha(ROOT/row['file'])==row['sha256']
    lists=read(HERE/'dat_candidate_lists.json');capacity=read(HERE/'capacity_safe_profile.json')
    profile=lists['capacity_safe_same_release_test_profile']
    assert profile['sha256']==sha(HERE/'capacity_safe_profile.json')
    assert capacity['published_looks_removed']==0 and capacity['required_five_shared_refits_preserved']
    replacements={(r['unit'],r['name']):HERE/r['record_file'] for r in capacity['selected']}
    for row in capacity['selected']:assert sha(HERE/row['record_file'])==row['record_sha256']
    counted=base.table_cost(replacements);assert counted==capacity['row_accounting']
    assert all(p['over_limit_bytes']==0 for p in counted['packages'])
    chosen={(r['unit'],r['index']) for r in capacity['selected']}
    assert {('mount-a12',22),('mount-a12',23),('mount-a12',24),('a12-50',21),('a12-50',26)}<=chosen
    assert (('a12-50',19) in chosen)==(('a12-50',29) in chosen)
    D=base.decoder();stock=base.records()
    for unit,items in stock.items():
        for row in items:
            if row['kind']!='look':continue
            record=replacements.get((unit,row['name']),HERE/row['record_file']).read_bytes()
            native=next(r for r in items if r['kind']=='builtin' and r['slot']==record[0])
            parent=replacements.get((unit,native['name']),HERE/native['record_file']).read_bytes()
            assert record[1]==parent[1]
    print(json.dumps(dict(status='PASS',probe2_profiles=35,local_full_start_exact=27,
        shared_or_native_unchanged=8,conditional_record_changes=summary['changed_records'],
        all105_primary_record_SHAs_unchanged_since_priority_checkpoint=True,
        source_files_rehashed=len(source['files']),photo_files_rehashed=len(source['photo_inputs']) if photos else 0,
        capacity_profile_records=len(capacity['selected']),capacity_profiles_fit=True,
        no_new_hardware_or_camera_acceptance_claim=True,no_DAT_built=True),ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--photos',action='store_true');main(ap.parse_args().photos)
