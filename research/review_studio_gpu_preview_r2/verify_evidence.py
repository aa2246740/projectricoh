"""Fail closed when a report claim is not supported by the saved observations."""
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent
WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')
read=lambda name:json.loads((HERE/name).read_text())
checks={}
colour={}
for mode,adapter in [('metal','metal-3'),('swiftshader','swiftshader')]:
    rows=read(f'real-parity-{mode}.json');ind=read(f'independent-parity-{mode}.json')
    route=read(f'real-route-{mode}.json')
    assert len(rows)==len(ind)==len(route['result'])==14
    assert route['actualAdapters']==[adapter] and not route['errors']
    assert all(r['way']=='gpu' for r in route['result'])
    for a,b in zip(rows,ind):
        assert a['id']==b['id'] and a['pass']
        assert a['over_1']*10000<=a['pixels'] and a['mean_de00']<=.01
        assert a['max_out_band']<=4 and a['over_2_in_band']<=math.ceil(a['pixels']*1e-6)
        assert a['over_1']==b['over_1_pixels'] and a['pixels']==b['pixels'] and a['max_code']==b['max_code']
        assert math.isclose(a['mean_de00'],b['mean_delta_e00'],rel_tol=1e-12,abs_tol=1e-15)
        if a['over_2_out_band']:
            assert len(a['over_2_out_band'])==len(a['explained'])==7 and all(a['explained'])
            assert a['forward_proof']=='actual_gpu_first_stage_through_production_apply_extra'
    trace=read(f'rounding-trace-{mode}.json')
    assert trace['over_2_pixels']==7 and all(p['explains_final_exactly'] for p in trace['points'])
    synthetic=read(f'synthetic-lut-counterexample-{mode}.json')
    assert synthetic['adapter']['info']['architecture']==adapter
    assert len(synthetic['rows'])==2 and all(r['over_1_pixels']==0 and r['mean']==0 and r['max_code']==0 for r in synthetic['rows'])
    colour[mode]={'real_cases':14,'synthetic_counterexamples':2,'all_pass':True}
checks['colour_and_actual_forward_proof']=True
exhaustive=read('exhaustive-lut.json')
assert len(exhaustive)==2 and all(r['inputs']==256**3 and r['mismatching_pixels']==r['alpha_mismatches']==r['max_code']==0 for r in exhaustive)
checks['full_256_cubed_lut_comparison']=True
assert read('baseline-comparison.json')['all_pass']
assert read('flag-off-api-probe.json')=={'status':200,'response':{'enabled':False},'raw_layout_calls':0,'warm_preview_calls':0}
off=next(r for r in read('fallback-probes.json') if r['mode']=='flag_off')
assert off['gpuRequests']==off['adapterCalls']==off['deviceCalls']==0 and off['img'] and off['status']==200
checks['flag_off_render_and_request_regression']=True
assert all(r['pass'] for r in read('lut-ui-lifecycle.json'))
cam=read('camdata-ui-probe.json')
assert not cam['staleUI'] and cam['current']['key']==cam['newBakeKey'] and cam['current']['hash']==cam['forcedFreshTable']['hash']
checks['normal_camera_and_lut_generations']=True
prefetch=read('prefetch-generation.json')
assert len(prefetch['rows'])==2 and all(r['pass'] and r['oldStarted'] for r in prefetch['rows'])
checks['late_prefetch_generation_model']=True
api=read('api-probes.json')
assert len([r for r in api if 'pass' in r])==24 and all(r['pass'] for r in api if 'pass' in r)
assert all(not r['outside_bytes_returned'] and r['status']==409 for r in api if r['case']=='outside_symlink')
assert all(r['status']==422 for r in api if r['case'] in ('invalid_crop','nan_crop'))
assert next(r for r in api if r['case']=='legacy_lut_read_side_effect')['writes']==[]
readonly=read('real-api-readonly.json')
assert readonly['writes']==[] and len(readonly['responses'])==6 and all(r['status']==200 for r in readonly['responses'])
checks['old_api_counterexamples_and_read_only']=True
tables=read('table-resource-probe.json')
assert tables['overwrite']['texturesDestroyed']==tables['overwrite']['buffersDestroyed']==11
assert tables['capped']['stats']['luts']==3 and tables['capped']['stats']['bakes']==24
assert tables['disposed']['liveTableBytes']==tables['disposed']['liveBakeBytes']==0
resources=read('resource-probe.json')
assert resources['beforeDispose']['sourceBytes']<=resources['budget']
assert resources['afterDispose']['texturesCreated']==resources['afterDispose']['texturesDestroyed']==17
assert resources['afterDispose']['buffersCreated']==resources['afterDispose']['buffersDestroyed']==34
checks['resource_ownership_and_caps']=True
tests={}
for name in ['make-check','path-io-full']:
    suites=ET.parse(HERE/(name+'.xml')).getroot().findall('testsuite')
    totals={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','errors','failures','skipped']}
    assert totals=={'tests':1695,'errors':0,'failures':0,'skipped':697},totals
    assert read(name+'-receipt.json')['exit_code']==0
    tests[name]=totals
coverage=read('coverage.json')['totals']['percent_covered']
assert coverage>=85
checks['full_tests_zero_reruns']=True
bugs={}
http=read('http-boundary-extra.json')
assert sum(r.get('outside_bytes_returned',False) for r in http)==2
assert next(r for r in http if r['case']=='root_replaced_during_raw_layout_open')['parsed_external_layout']
bugs['P1-01_remaining_root_open_race']=True
assert read('lut-reimport-probe.json')['wrong_current_table']
bugs['P1-02_remaining_lut_incarnation_collision']=True
delete=read('path-delete-race.json')
assert delete[0]['outside_file_survives'] and not delete[1]['outside_file_survives'] and delete[1]['error'] is None
bugs['R2-P1-01_path_delete_boundary']=True
card=read('card-reader-retarget.json')
assert card[1]['outside_bytes_read'] and not card[0]['outside_bytes_read'] and card[1]['scan_complete'] and not card[1]['errors']
assert card[1]['production_read_head_calls'][0]['name']=='.DS_Store'
assert card[1]['photos'][0]['relpath'].endswith('OUTSIDE.JPG') and card[0]['photos'][0]['relpath'].endswith('OWN.JPG')
bugs['R2-P1-02_card_reader_directory_retarget']=True
range_bug=next(r for r in http if r['case']=='range_integer_overflow')
assert range_bug['fd_growth']==range_bug['request_count']==12 and range_bug['statuses']==[500]*12
bugs['R2-P2-01_range_fd_leak']=True
assert read('build-byte-comparison.json')['all_bytes_equal'] and read('public-bytes-independent.json')['pass']
checks['build_bytes_and_public_artifacts']=True
frozen=read('frozen-inputs.json')
changed=[p for p,digest in frozen['files'].items() if not (WT/p).is_file() or hashlib.sha256((WT/p).read_bytes()).hexdigest()!=digest]
head=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'rev-parse','HEAD']).decode().strip()
status=subprocess.check_output(['git','--no-optional-locks','-C',str(WT),'status','--short','--untracked-files=all']).decode()
assert not changed and head==frozen['head'] and status==(HERE/'initial-status.txt').read_text()
stability={'head':head,'tracked_files':len(frozen['files']),'changed_files':changed,'status_unchanged':True,'scope':'tracked source; preexisting ignored cache update is documented separately'}
(HERE/'source-stability.json').write_text(json.dumps(stability,indent=2)+'\n')
summary={'checks':checks,'tests':tests,'coverage_percent':coverage,'colour':colour,'confirmed_findings':bugs,'p1_count':4,'p2_new_count':1,'source_stability':stability}
(HERE/'verified-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
