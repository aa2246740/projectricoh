"""Check final review evidence and summarize the independently rerun cases."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scope

dat='175716c818a0db37c0deaac5feefbb6b56bb4571185dbb566585549e43fb0622'
assert (HERE/'REVIEW.md').read_text().splitlines()[0]=='不能上卡'
artifact=json.loads((HERE/'artifact-review.json').read_text())
static=json.loads((HERE/'static-diag147.json').read_text())
lock=json.loads((HERE/'lock-proof.log').read_text())
assert artifact['status']=='PASS_STATIC_ARTIFACT' and artifact['dat_sha256']==dat
assert static['status']=='PASS' and static['dat_sha256']==dat
assert lock['status']=='PASS' and len(lock['mutants'])==4
assert all(row['caught'] for row in lock['mutants'].values())
jobs=[('full','50mm'),('full','28mm'),('full','mount'),('faults','50mm'),('keep1','50mm')]
rows=[]
total=dict(tries=0,taken=0,signals=0,not_taken=0)
for case,unit in jobs:
    report=HERE/'local'/('accept147-%s-%s.json'%(case,unit))
    value=json.loads(report.read_text())
    receipt=json.loads((HERE/('host-%s-%s-receipt.json'%(case,unit))).read_text())
    assert receipt['exit_code']==0 and value['dat']==dat
    assert value['rpc_w']==0 and not value['s_writes'] and value['s_hash_same']
    assert value['card_writes']==0 and value['card_unchanged']
    assert not value['violations'] and not value['creates_renames_deletes']
    for key in total:
        total[key]+=value['lock'][key]
    rows.append(dict(case=case,unit=unit,status='PASS',reads=len(value['reads']),
                     seconds=receipt['elapsed_seconds'],result=str(report.relative_to(scope.ROOT))))
assert total==dict(tries=25,taken=23,signals=23,not_taken=2)
scope.save(HERE/'host-suite.json',dict(
    counts=dict(PASS=5,FAIL=0,INCOMPLETE=0),rows=rows,total_lock=total,
    limits='Native card internals and ticks are models; not a physical-card zero-write proof.'))
native=json.loads((HERE/'native-review.json').read_text())
assert len(native['cases'])==19 and native['status']=='PASS_BOUNDED_NATIVE_CONTROL_FLOW'
device=json.loads((HERE/'cache-review-device.json').read_text())
assert device['actual_buffer_flush'] and device['actual_device_dispatch']
assert device['pending_cluster_queue'] and device['ready_cluster_pool'] and device['dat_sha256']==dat
case=device['cases'][0]
assert not case['initial_fat_setter'] and not case['other_file_dirty']
assert case['writer_committed_fat_entries'] and case['writer_wrapper_released47']
assert case['other_file_dirty_after_writer']==1
assert case['first_request']['kind']=='write'
assert case['first_request']['args']==[0,32,3,0x204c922c]
assert case['first_request']['reader_file_dirty']==0 and case['first_request']['reader_flags']==0x82
ordinary=json.loads((HERE/'cache-review-real.json').read_text())
assert all(case['first_request']['args'][1]==1 for case in ordinary['cases'])
receipts=[]
for file in sorted(HERE.glob('*-receipt.json')):
    value=json.loads(file.read_text())
    receipts.append(dict(name=file.name,**value))
scope.save(HERE/'runs-index.json',dict(
    runs=receipts,
    note='Nonzero review-script runs remain failures. Final native/model observations are identified separately; host acceptance counts contain only the five requested scenarios.'))
scope.save(HERE/'final-checks.json',dict(
    status='PASS_REVIEW_EVIDENCE',verdict='不能上卡',blocking_findings=['D147-01'],
    dat_sha256=dat,host_scenarios=5,native_cases=19,lock_mutants_caught=4,
    native_lookup_reached_write_device_callback=True,
    device_callback='0x200a3358',synthetic_write_lba=32,synthetic_write_sectors=3,
    physical_card_executed=False,reviewed_firmware_modified=False))
print('FINAL_CHECKS_DONE',dat,flush=True)
