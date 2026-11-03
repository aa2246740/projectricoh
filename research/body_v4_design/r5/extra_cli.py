#!/usr/bin/python3 -I -B
"""Fresh interpreter checks for positives, old CLI inputs and changed source evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fixtures import gate,encode,load_module
from public_runner import arguments
from run_mutations import assert_incomplete

BASE=HERE.parent;ROOT=BASE.parents[1]
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r5')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and SCRATCH.is_dir()
    checker=BASE/'r3/diag_gate.py';rows=[]
    index=json.loads((HERE/'positive-index.json').read_text())
    for case in index:
        raw=(HERE/'positive'/(case['stem']+'-record.json')).read_text()
        ran=subprocess.run(['/usr/bin/python3','-I','-B',str(checker)]+arguments(case),
                           input=raw,capture_output=True,text=True,timeout=60)
        actual=json.loads(ran.stdout)
        assert ran.returncode==0 and ran.stderr=='' and actual['records_complete'] is True,(case['name'],ran)
        assert actual['er_ownership']=='not_established_by_diag' and actual['h42_time']=='requires_final_v4_measurement'
        rows.append(dict(name=case['name'],group='complete',exit=0,result=actual))
    gold=gate.read_json(HERE/'positive/00-record.json')
    profile=gate.read_json(HERE/'positive/00-profile.json')
    capture=gate.read_json(HERE/'positive/00-capture.json')
    ppath=SCRATCH/'extra-profile.json';cpath=SCRATCH/'extra-capture.json'

    def run(name,content,p=None,c=None,profile_pin=None,capture_pin=None,missing=False,expected_code=None):
        p=copy.deepcopy(profile) if p is None else p
        c=copy.deepcopy(capture) if c is None else c
        c['record_sha256']=hashlib.sha256(content.encode()).hexdigest()
        ppath.write_bytes(encode(p));cpath.write_bytes(encode(c))
        argv=[str(SCRATCH/'absent-record.json') if missing else '-',
              '--profile',str(ppath),'--profile-sha256',profile_pin or hashlib.sha256(encode(p)).hexdigest(),
              '--capture',str(cpath),'--capture-sha256',capture_pin or hashlib.sha256(encode(c)).hexdigest()]
        ran=subprocess.run(['/usr/bin/python3','-I','-B',str(checker)]+argv,
                           input=content,capture_output=True,text=True,timeout=60)
        assert ran.returncode==2 and ran.stderr=='',(name,ran.returncode,ran.stderr,ran.stdout)
        actual=json.loads(ran.stdout);assert_incomplete(actual)
        code=actual['reasons']['record'][0]['code']
        assert code!='frozen_record_changed',(name,code)
        if expected_code:assert code==expected_code,(name,actual)
        rows.append(dict(name=name,group='incomplete',exit=ran.returncode,result=actual,
                         input_sha256=hashlib.sha256(content.encode()).hexdigest()))

    cases=json.loads((ROOT/'research/review_v4_design_r2/record-variants.json').read_text())['variants'][1:]
    factory=load_module('extra_cli_old_factory',BASE/'r4/record_cases.py')
    for case in cases:
        run('old_original_'+case['name'],encode(case['input']).decode())
        run('old_rebased_'+case['name'],encode(factory.apply_review_variant(copy.deepcopy(gold),case['name'])).decode())
    raw=encode(gold).decode()
    run('old_wrong_reference_hash',raw,profile_pin='0'*64)
    p=copy.deepcopy(profile);p['qualities']['raw_jpeg']['category_ids'].remove(1)
    run('old_reference_changed_with_prior_hash',raw,p=p,profile_pin=hashlib.sha256(encode(profile)).hexdigest(),expected_code='profile_hash_mismatch')
    run('old_duplicate_json_member','{"frozen":true,'+raw[1:],expected_code='duplicate_json_member')
    run('old_nonfinite_json_number',raw.replace('"frozen":true','"frozen":NaN',1),expected_code='nonfinite_json_number')
    run('old_truncated_json',raw[:90],expected_code='json_or_file_invalid')
    run('old_missing_file',raw,missing=True,expected_code='json_or_file_invalid')
    run('old_fixture_profile_for_device_record',encode(dict(gold,classification='device_capture')).decode(),expected_code='capture_scope_mismatch')
    p=copy.deepcopy(profile);p['control_crc32']+=1
    run('profile_crc_recomputed',raw,p=p,expected_code='derived_value_mismatch')
    p=copy.deepcopy(profile);p['r5_unknown']=1
    run('unknown_profile_member',raw,p=p,expected_code='unknown_field')
    c=copy.deepcopy(capture);c['r5_unknown']=1
    run('unknown_capture_member',raw,c=c,expected_code='unknown_field')
    run('capture_hash_mismatch',raw,capture_pin='0'*64,expected_code='capture_hash_mismatch')
    for name,edit in (
        ('source_file_length',lambda c:c['observations']['file_segments'][0].update(repeats=20481)),
        ('source_pool_cursor',lambda c:c['observations']['slot_scans'][0].update(pool_cursor=0x87f7bb31)),
        ('source_inactive_row',lambda c:c['observations']['slot_scans'][0]['rows'][98].update(count_raw=1)),
        ('source_osd_checksum',lambda c:c['observations']['osd_reads'][0].update(segments=[dict(pattern='01000000',repeats=1),dict(pattern='00',repeats=153596)])),
        ('source_control_checksum',lambda c:next(r for r in c['observations']['bw_reads'] if r['kind']=='control').update(segments=[dict(pattern='01000000',repeats=1),dict(pattern='00',repeats=65532)])),
        ('source_crc_checksum',lambda c:next(r for r in c['observations']['bw_reads'] if r['kind']=='crc').update(segments=[dict(pattern='00',repeats=65536)])),
    ):
        c=copy.deepcopy(capture);edit(c)
        run(name,raw,c=c,expected_code='derived_value_mismatch')
    result=dict(complete=54,incomplete=sum(row['exit']!=0 for row in rows),cases=rows,
                fresh_interpreter_for_every_case=True,
                checker_sha256=hashlib.sha256(checker.read_bytes()).hexdigest(),
                contract_sha256=hashlib.sha256((HERE/'derived_contract.py').read_bytes()).hexdigest(),
                runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (HERE/'fresh-cli-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(complete=result['complete'],incomplete=result['incomplete'],all_passed=True)))


if __name__=='__main__':main()
