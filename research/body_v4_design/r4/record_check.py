#!/usr/bin/python3 -I -B
"""Behavior checks for complete, incomplete and differently bound records."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'r3'))
sys.path.insert(0,str(HERE))
from diag_gate import classify,load_profile,InvalidRecord,read_json
from record_cases import (encoded,profile_data,complete_records,interleaved_records,apply_review_variant,record)


def location(path):
    return '$'+''.join(f'[{k}]' if type(k) is int else '.'+k for k in path)


def paths(value,path=()):
    if type(value) is dict:
        for key,item in value.items():
            yield path+(key,),item
            yield from paths(item,path+(key,))
    elif type(value) is list:
        for index,item in enumerate(value):
            yield path+(index,),item
            yield from paths(item,path+(index,))


def parent(doc,path):
    target=doc
    for key in path[:-1]: target=target[key]
    return target,path[-1]


def change(doc,scene,path,value):
    target,key=parent(record(doc,scene),path)
    target[key]=copy.deepcopy(value)


def legacy_variants(base,description):
    for case in description['cases']:
        doc=copy.deepcopy(base)
        change(doc,case['scene'],case['path'],case['value'])
        yield case['case'],doc
    for name in ('missing_scene','not_frozen','invalid_shape','no_osd_difference'):
        doc=copy.deepcopy(base)
        if name=='missing_scene': del doc['records'][0]
        elif name=='not_frozen': doc['frozen']=False
        elif name=='invalid_shape': doc['records']=[None]
        else: change(doc,'GRID_ON',['layers',2,'rectangles'],[])
        yield name,doc


def run_checks(write=False):
    if write:
        source=profile_data()
        (HERE/'reference-profile.json').write_bytes(encoded(source))
        (HERE/'reference-profile.sha256').write_text(hashlib.sha256(encoded(source)).hexdigest()+'\n')
        (HERE/'complete-records.json').write_bytes(encoded(complete_records(source)))
    raw_profile=read_json(HERE/'reference-profile.json')
    expected_hash=(HERE/'reference-profile.sha256').read_text().strip()
    reference=load_profile(raw_profile,expected_hash)
    gold=read_json(HERE/'complete-records.json')
    assert encoded(raw_profile)==encoded(profile_data())
    assert encoded(gold)==encoded(complete_records(raw_profile))
    result=classify(gold,reference)
    assert result['record_stage']=='records_complete_for_offline_review'
    assert result['records_complete'] is True and result['verdict']=='记录齐全，可交离线复核'
    assert result['read_interval']['elapsed_ms']==[160,224]
    assert result['control_interval']['samples']==32 and result['crc_interval']['samples']==32
    checks=[]

    def reject(group,name,doc,profile=reference,expected_code=None):
        actual=classify(doc,profile)
        assert actual['record_stage']=='undetermined' and actual['records_complete'] is False,(name,actual)
        assert actual['verdict']=='不完整、不通过',(name,actual)
        assert [actual[k] for k in ('capacity','h43','time')]==['undetermined']*3,(name,actual)
        assert [actual[k] for k in ('read_interval','control_interval','crc_interval')]==[None]*3
        assert actual['er_ownership']=='not_established_by_diag'
        assert actual['h42_time']=='requires_final_v4_measurement'
        issue=actual['reasons']['record'][0]
        if expected_code: assert issue['code']==expected_code,(name,issue)
        checks.append(dict(group=group,name=name,record_stage=actual['record_stage'],issue=issue))

    reviewed=json.loads((ROOT/'research/review_v4_design_r2/record-variants.json').read_text())
    names=[r['name'] for r in reviewed['variants'][1:]]
    for case in reviewed['variants'][1:]: reject('review_original_6',case['name'],case['input'])
    reject('review_control','missing_common_record_field',reviewed['variants'][0]['input'])
    expected_codes=['required_field_missing','required_field_missing','reference_category_coverage_missing',
                    'integer_range_invalid','required_field_missing','shot_identity_mismatch']
    for name,code in zip(names,expected_codes):
        doc=apply_review_variant(copy.deepcopy(gold),name)
        reject('review_rebased_6',name,doc,expected_code=code)
    prior=json.loads((HERE/'before/diag-fixtures.json').read_text())
    for name,doc in legacy_variants(prior['base'],prior): reject('legacy_original_28',name,doc)
    for name,doc in legacy_variants(gold,prior): reject('legacy_rebased_28',name,doc)
    reject('legacy_positive_retired','simplified_r3_base',prior['base'])

    for path,value in paths(gold):
        if type(path[-1]) is str:
            doc=copy.deepcopy(gold);target,key=parent(doc,path);del target[key]
            reject('required_field_delete',location(path),doc,expected_code='required_field_missing')
        wrong=False if type(value) is int else (None if value is not None else '')
        doc=copy.deepcopy(gold);target,key=parent(doc,path);target[key]=wrong
        reject('wrong_type',location(path),doc)
        if type(value) is list and value:
            doc=copy.deepcopy(gold);target,key=parent(doc,path);del target[key][0]
            reject('array_item_delete',location(path),doc)

    for path,value in paths(gold):
        if type(value) is dict and set(value)=={'boot','unit','unit_epoch','set','scene_id','config_version'}:
            for key in value:
                doc=copy.deepcopy(gold);target,last=parent(doc,path)
                target[last][key]='mount' if key=='unit' else value[key]+1
                reject('nested_identity_mismatch',location(path+(key,)),doc,
                       expected_code='scene_identity_mismatch')

    semantic=[]
    def case(name,fn):
        doc=copy.deepcopy(gold);fn(doc);semantic.append((name,doc))
    case('missing_scene_snapshot',lambda d:record(d,'KEY')['snapshots'].pop(1))
    case('all_controlled_settings_changed',lambda d:record(d,'GRID_ON')['other_settings'].update(info_frame=1))
    case('same_unknown_osd_quality',lambda d:[record(d,s)['other_settings'].update(quality_id=999)
                                             for s in ('GRID_OFF','GRID_ON','INFO_OFF','INFO_ON')])
    case('missing_native_resource',lambda d:record(d,'RAW_L')['resources'].pop())
    case('wrong_native_rule',lambda d:record(d,'JPEG_L').update(native_rule='7'*64))
    case('physical_scan_stops_at_32',lambda d:record(d,'RAW_L').update(covered_mask=f'{(1<<32)-1:032x}'))
    case('inactive_row_nonzero',lambda d:record(d,'RAW_L').update(inactive_nonzero_mask=f'{1<<98:032x}'))
    case('unknown_extra_category',lambda d:record(d,'JPEG_L')['category_ids'].append(98))
    case('duplicate_category',lambda d:record(d,'RAW_L')['categories'].__setitem__(0,
                                                 copy.deepcopy(record(d,'RAW_L')['categories'][1])))
    case('single_slot_without_stride',lambda d:record(d,'JPEG_L')['categories'][1].update(stride_source='verified_adjacent'))
    case('stride_field_is_not_address_matrix',lambda d:record(d,'JPEG_L')['categories'][1].update(stride_address=0x205785ac))
    case('image_range_too_short',lambda d:record(d,'RAW_169')['image'].update(range=[0x81000000,0x81000100]))
    case('image_source_not_whitelisted',lambda d:record(d,'JPEG_L')['image'].update(source=0x20000000))
    case('scene_number_relabelled',lambda d:record(d,'RAW_169').update(scene_id=7))
    case('record_sequence_gap',lambda d:record(d,'RAW_L').update(sequence=77))
    case('snapshot_sequence_gap',lambda d:record(d,'KEY')['snapshots'][1].update(sequence=3))
    case('osd_piece_sequence_gap',lambda d:record(d,'GRID_ON')['layers'][0]['pieces'][1].update(sequence=3))
    case('osd_piece_overlap',lambda d:record(d,'GRID_ON')['layers'][0]['pieces'][1].update(offset=0))
    case('bw_piece_sequence_gap',lambda d:record(d,'BW')['read_samples'][1].update(sequence=3))
    case('photo_sequence_gap',lambda d:record(d,'RAW_169')['image'].update(sequence=120))
    case('burst_sequence_gap',lambda d:record(d,'BURST')['samples'][1].update(sequence=200))
    case('crc_time_zero',lambda d:record(d,'BW')['crc_samples'][0].update(end_tick=record(d,'BW')['crc_samples'][0]['start_tick']))
    case('crc_result_wrong_with_ok_flag',lambda d:record(d,'BW')['crc_samples'][0].update(result=1))
    case('control_time_summary_not_raw_delta',lambda d:record(d,'BW')['control_ticks'].__setitem__(0,7))
    case('er_source_is_bss',lambda d:record(d,'BW')['read_samples'][0].update(range=[0x20710000,0x20750000]))
    case('control_source_outside_bss',lambda d:record(d,'BW').update(control_range=[0x20700000,0x20710000]))
    case('wrong_unit_header_only',lambda d:d['identity'].update(unit='mount'))
    case('wrong_unit_epoch_header_only',lambda d:d['identity'].update(unit_epoch=99))
    case('mem_before_is_earlier_shot',lambda d:record(d,'PLAY')['mem_before']['context'].update(scene_id=9))
    case('mem_order_reversed',lambda d:record(d,'PLAY')['mem_before'].update(tick=10890))
    case('positive_complete_flag_with_lost_item',lambda d:record(d,'BURST').update(lost=1))
    case('record_overwritten',lambda d:record(d,'GRID_OFF').update(overwritten=1))
    case('untrusted_profile_inside_capture',lambda d:d.update(profile=copy.deepcopy(raw_profile)))
    case('pool_raw_fields_disagree_with_bounds',lambda d:record(d,'JPEG_L')['raw_fields'].update(p_ec=0))
    case('osd_piece_time_reversed',lambda d:record(d,'GRID_ON')['layers'][0]['pieces'][0].update(start_tick=3030,end_tick=3035))
    case('controlled_pair_time_reversed',lambda d:record(d,'GRID_ON').update(start_tick=2500,end_tick=3900))
    case('bw_piece_time_reversed',lambda d:record(d,'BW')['read_samples'][0].update(start_tick=11024,end_tick=11030))
    case('burst_photo_time_reversed',lambda d:record(d,'BURST')['samples'][0].update(h09=9250,h40=9260,h41=9270))
    def reuse_lifetime(doc):
        sample=record(doc,'BURST')['samples'][0]
        first=record(doc,'JPEG_L')['image']
        for key in ('h09_key','h40_key','h41_key'):
            sample[key][2:]=[first['k'],first['k_life']]
    case('same_k_reuses_previous_photo_lifecycle',reuse_lifetime)
    for name,doc in semantic: reject('same_class_semantic',name,doc)
    reject('reference_boundary','reference_not_supplied',gold,profile=None)
    changed_profile=copy.deepcopy(raw_profile)
    changed_profile['qualities']['raw_jpeg']['category_ids'].remove(1)
    try: load_profile(changed_profile,expected_hash)
    except InvalidRecord as error:
        assert error.code=='profile_hash_mismatch'
        checks.append(dict(group='reference_boundary',name='changed_reference_with_old_hash',
                           record_stage='undetermined',issue=dict(path=error.path,code=error.code)))
    else: raise AssertionError('changed reference accepted')
    assert reference.data==raw_profile
    changed_copy=reference.data;changed_copy['unit']='mount'
    assert reference.data['unit']=='50mm'

    positives=['complete_50mm']
    for unit in ('28mm','mount'):
        raw=copy.deepcopy(raw_profile);raw['unit']=unit
        doc=complete_records(raw)
        def set_unit(value):
            if type(value) is dict:
                for key,item in value.items():
                    if key=='unit': value[key]=unit
                    else: set_unit(item)
            elif type(value) is list:
                for item in value:set_unit(item)
        set_unit(doc)
        ref=load_profile(raw,hashlib.sha256(encoded(raw)).hexdigest())
        assert classify(doc,ref)['records_complete'] is True
        positives.append('complete_synthetic_'+unit)
        reject('reference_boundary','unit_self_consistent_wrong_profile_'+unit,doc)
    wrapped=copy.deepcopy(gold)
    tick_names={'start_tick','end_tick','tick','ready_tick','h09','h40','h41'}
    for path,value in list(paths(wrapped)):
        if path[-1] in tick_names:
            target,key=parent(wrapped,path);target[key]=(value-1010)&0xffffffff
    assert classify(wrapped,reference)['records_complete'] is True
    positives.append('complete_tick_wrap_and_zero_timestamp')
    reordered=copy.deepcopy(gold)
    for scene in ('JPEG_L','RAW_L'):record(reordered,scene)['categories'].reverse()
    assert classify(reordered,reference)['records_complete'] is True
    positives.append('complete_categories_reported_in_different_order')
    interleaved=interleaved_records(gold)
    assert classify(interleaved,reference)['records_complete'] is True
    positives.append('complete_interleaved_photos_with_unique_identity')
    for valid in (gold,wrapped,reordered,interleaved):
        actual=classify(valid,reference)
        assert actual['er_ownership']=='not_established_by_diag'
        assert actual['h42_time']=='requires_final_v4_measurement'
    counts={}
    for row in checks:counts[row['group']]=counts.get(row['group'],0)+1
    assert counts['review_original_6']==counts['review_rebased_6']==6
    assert counts['legacy_original_28']==counts['legacy_rebased_28']==28
    detail=dict(classification='host_record_contract_only',positive_cases=positives,
                incomplete_cases=checks,counts=counts,records_complete_false=len(checks))
    detail_bytes=json.dumps(detail,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n'
    summary=dict(base=gold,cases=[r for r in checks if r['group'] in ('review_rebased_6','legacy_rebased_28')],
                 positive_stage='records_complete_for_offline_review',positive_cases=positives,
                 record_cases_rejected=len(checks),counts=counts,
                 detail_sha256=hashlib.sha256(detail_bytes).hexdigest(),
                 detail_path='r4/record-sensitivity.json',read_interval=result['read_interval'],
                 h42_time_passes=0,er_ownership_passes=0)
    if write:
        (HERE/'record-sensitivity.json').write_bytes(detail_bytes)
        (HERE/'record-results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    else:
        assert (HERE/'record-sensitivity.json').read_bytes()==detail_bytes
        assert json.loads((HERE/'record-results.json').read_text())==summary
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--write-evidence',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    assert args.write_evidence != args.check
    result=run_checks(write=args.write_evidence)
    print(json.dumps(dict(positive_cases=len(result['positive_cases']),negative_cases=result['record_cases_rejected'],
                          counts=result['counts']),ensure_ascii=False))


if __name__=='__main__':main()
