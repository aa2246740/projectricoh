"""Verify delivered evidence and optionally remove only the declared scratch tree.

No subprocess, Git, card, network or owner-Studio access. Source-tree drift is
reported separately from changes to files actually read by accepted runs.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
c.guard(900,require_tmp=False)


def read(name):return json.loads((c.HERE/name).read_text())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cleanup',action='store_true');args=ap.parse_args()
    rows=read('inference_results.json');assert len(rows)==60 and not any('error' in r for r in rows)
    groups=Counter(r['group'] for r in rows)
    assert groups=={'street-g137':8,'chart-g150':9,'scene-g150':7,'chart-50mm-old':36}
    street=[r for r in rows if r['group']=='street-g137']
    assert sum(r['correct'] for r in street)==7
    missed=next(r for r in street if not r['correct'])
    assert missed['file']=='R8051537' and missed['truth']=='08' and missed['best']=='07' and missed['quality']=='uncertain'
    assert sum(r['correct'] for r in rows)==59
    assert sum(r['correct'] and len(r['aliases'])==1 for r in rows)==58
    assert all(r['correct'] for r in rows if r['quality']=='supported')
    assert sum(r['quality']=='supported' for r in rows)==48
    photos={}
    for row in rows:
        folder=c.ROOT/row['folder'];sub='street-' in row['group']
        for suffix,key,child in [('.DNG','dng_sha256','dng'),('.JPG','jpg_sha256','jpg')]:
            p=folder/(child if sub else '')/(row['file']+suffix)
            assert c.sha(p)==row[key]
            photos[str(p.relative_to(c.ROOT))]=row[key]
    for group,value in read('jpg_only_results.json')['summary'].items():assert value=={'n':8,'correct':1}
    assert all(r['equal'] for r in read('candidate_equality.json').values())
    inventory=read('metadata_inventory.json');assert len(inventory)==69
    assert all(r['fields']['UserComment']['count']==264 and r['fields']['UserComment']['empty'] for r in inventory)
    for r in inventory:assert c.sha(c.ROOT/r['path'])==r['sha256']
    checks=read('metadata_copy_checks.json');assert checks['single_byte_mutations_rejected']==264
    assert len(checks['checks'])==2 and all(r['image_data_equal'] and r['only_usercomment_changed'] for r in checks['checks'])
    for side in ('c','python'):
        r=read('native_metadata_'+side+'.json');assert r['status']=='PASS' and len(r['rows'])==6
        if side=='c':assert r['execution_stats']['instructions']>0
        assert all(v['copied_template_exactly'] and v['neighbours_unchanged'] for v in r['rows'])
        r=read('log_wrapper_'+side+'.json');assert r['status']=='PASS' and len(r['rows'])==4
        if side=='c':assert all(v['execution_stats']['instructions']>0 for v in r['rows'])
        assert r['rows'][0]['commits'][0]['low_position']==75 and r['rows'][0]['commits'][0]['request_bytes']==150
        assert r['rows'][0]['model_file_length']==225 and r['rows'][1]['model_file_equals_two_lines']
        assert r['rows'][2]['close_result']==-1 and r['rows'][2]['post_close_high_handle_count']==1
        assert r['rows'][3]['model_file_equals_two_lines'] and r['rows'][3]['high_position_before_close']==75
    first=read('native_log.json');assert first['append']['actual_bytes']==225 and not first['append']['byte_equal']
    rewrite=read('native_log_rewrite.json');assert rewrite['status']=='PASS' and rewrite['append']['actual_bytes']==150
    direct=read('native_log_direct.json');assert direct['status']=='CONFIRMED_DIRECT_CONTENT_MISMATCH'
    assert direct['append']['actual_bytes']==150 and not direct['append']['byte_equal']
    assert rewrite['checks'][-1]['name']=='same-instance-native-reopen-read' and rewrite['checks'][-1]['bytes']==150
    failed_image=gzip.decompress((c.HERE/'local/first-append-failure.img.gz').read_bytes())
    assert hashlib.sha256(failed_image).hexdigest()==read('local/first-append-failure-image.json')['sha256']
    failed_direct=gzip.decompress((c.HERE/'local/direct-append-failure.img.gz').read_bytes())
    assert hashlib.sha256(failed_direct).hexdigest()==read('local/direct-append-failure-image.json')['sha256']
    assert read('initial-native-log-remount.json')['status']=='INCOMPLETE'
    assert len(read('log_matching_results.json')['checks'])==12
    static=read('static_evidence.json');assert len(static['windows'])==13 and all(r['v39_equal'] for r in static['windows'])
    assert all(r['v39_equal'] for r in static['template_bytes'].values())
    size=read('encoder_size.json');assert size['allocated_bytes']==680 and size['source_sha256']==c.sha(c.HERE/'tag_encoder.c')
    assert read('encoder_host_check.json')['cases']==104 and read('encoder_host_check.json')['byte_equal_to_python']
    visual=read('visual_data.json')
    assert visual['n']==8 and visual['correct']==7 and visual['matrix'][7][6]==1
    assert visual['source_sha256']==c.sha(c.HERE/'inference_results.json')
    # Keep the actual small measured artifacts after Scratch is removed.
    for src,dst,key,receipt in [('tag_encoder.o','tag_encoder.o','object_sha256',size),
                              ('libtag_encoder.dylib','libtag_encoder.dylib','library_sha256',read('encoder_host_check.json'))]:
        p=c.TMP/src;q=c.HERE/'local'/dst
        if p.exists():
            assert c.sha(p)==receipt[key];shutil.copyfile(p,q)
        assert c.sha(q)==receipt[key]
    # These receipts cover accepted evidence, not intentionally retained initial failures.
    accepted=['inference','jpg-only','inference-limits','metadata','native-metadata-c','native-metadata-python',
              'log-wrapper-c','log-wrapper-python','native-log-rewrite','native-log-direct','log-matching','static','encoder-host','encoder-size','candidate-equality','visual']
    dependencies={
        'inference':['infer.py'], 'jpg-only':['jpg_only.py','infer.py'],
        'inference-limits':['inference_limits.py','infer.py'], 'metadata':['metadata.py'],
        'native-metadata-c':['native_metadata.py'], 'native-metadata-python':['native_metadata.py'],
        'log-wrapper-c':['log_wrapper.py','native_metadata.py','native_log.py'],
        'log-wrapper-python':['log_wrapper.py','native_metadata.py','native_log.py'],
        'native-log-rewrite':['native_log.py'], 'native-log-direct':['native_log.py'],
        'log-matching':['log_match.py'], 'static':['static_evidence.py'],
        'encoder-host':['check_encoder.py','metadata.py'], 'encoder-size':['measure_encoder.py'],
        'candidate-equality':['candidate_equality.py','infer.py'], 'visual':['render_results.py'],
    }
    tested={};receipt_checks=[]
    for name in accepted:
        r=read(name+'-receipt.json');assert not r['changed']
        for script in ['common.py']+dependencies[name]:
            assert r['research_scripts'][script]==c.sha(c.HERE/script),(name,script,'script changed after run')
        drift=[rel for rel,h in r['inputs'].items() if c.sha(c.ROOT/rel)!=h]
        tested.update(r['inputs']);receipt_checks.append(dict(name=name,current_input_drift=drift))
    assert not any(r['current_input_drift'] for r in receipt_checks),receipt_checks
    before=read('inputs_before.json')['sha256']
    tree_drift=[rel for rel,h in before.items() if not (c.ROOT/rel).is_file() or c.sha(c.ROOT/rel)!=h]
    protected_drift=[p for p in tree_drift if p.startswith('tools/gxr_emulator') or p.startswith('firmware/')]
    assert not protected_drift,protected_drift
    c.dump('audit.json',dict(status='PASS',checked_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       original_photo_files_verified=len(photos),metadata_files_verified=len(inventory),
       inference_pairs=60,independent_order_cohort=8,independent_correct=7,
       supported=48,supported_correct=48,initial_source_files=len(before),source_tree_drift=tree_drift,
       tested_inputs_verified=len(tested),accepted_run_receipts=receipt_checks,
       field_tests_run=False,card_access=False,camera_package_built=False,owner_studio_access=False,git_writes=False,
       standalone_formatter_object_built=True,
       execution_deviation='Initial parallel read-only searches and a process-list pipeline exceeded the strict 3-process limit',
       open='Full restart/remount, direct-write full Python media replay, complete photo chain, native integration, FAT32, physical power loss and camera acceptance'))
    if args.cleanup:
        count=total=0
        if c.TMP.exists():
            assert not c.TMP.is_symlink()
            files=sorted(c.TMP.rglob('*'),key=lambda p:len(p.parts),reverse=True)
            for p in files:
                if p.is_symlink():raise ValueError('Unexpected scratch symlink')
                if p.is_file():total+=p.stat().st_size;count+=1;p.unlink()
                elif p.is_dir():p.rmdir()
            c.TMP.rmdir()
        assert not c.TMP.exists()
        c.dump('cleanup.json',dict(status='PASS',scratch=str(c.TMP),removed_files=count,removed_bytes=total,
                                   scratch_absent=True,owned_worker_processes_running=0,
                                   note='All started command sessions drained before final cleanup; no other task processes stopped'))
    # Manifest includes this report and verifier; excludes itself and immutable earlier manifests.
    paths=sorted(p for p in c.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (c.HERE/'SHA256SUMS').write_text(''.join(c.sha(p)+'  '+str(p.relative_to(c.ROOT))+'\n' for p in paths))
    print(json.dumps(dict(status='PASS',pairs=len(rows),photo_files=len(photos),source_tree_drift=tree_drift,
                         manifest_files=len(paths),scratch_absent=not c.TMP.exists())))


if __name__=='__main__':main()
