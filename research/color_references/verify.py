#!/usr/bin/env python3
"""Check the actual artifacts, source hashes and numerical acceptance gates."""
import csv,hashlib,json,struct,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import numpy as np
from colour_math import delta_e00,srgb_decode,lab_xyz,xyz_lab,rgb_lab,common_white_sensor_bridge
from tiff_read import Tiff
from lossless_jpeg import decode
from evaluate_acceptance import score

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while block:=f.read(1024*1024):h.update(block)
    return h.hexdigest()

def main():
    checks={}
    for p in HERE.glob('*.json'):json.loads(p.read_text())
    checks['all_json_parse']=True
    a=np.array([[50,2.6772,-79.7751],[50,3.1571,-77.2803],[50,2.8361,-74.0200],[50,-1.3802,-84.2814],
                [50,-1.1848,-84.8006],[50,-.9009,-85.5211],[50,0,0]])
    b=np.array([[50,0,-82.7485]]*6+[[50,-1,2]])
    expected=np.array([2.0425,2.8615,3.4412,1.,1.,1.,2.3669])
    actual=delta_e00(a,b)
    assert np.max(np.abs(actual-expected))<5e-5
    assert np.max(delta_e00(a,a))==0
    checks['CIEDE2000_Sharmas_published_cases_max_abs_error']=float(np.max(np.abs(actual-expected)))
    full=np.loadtxt('/tmp/gxr_color_refs/downloads/ciede2000_testdata/testdata.txt')
    err=np.abs(delta_e00(full[:,:3],full[:,3:6])-full[:,6])
    assert len(full)==34 and err.max()<5.1e-5
    checks['CIEDE2000_full_34_cases_max_abs_error']=float(err.max())
    chart=json.loads((HERE/'screen_chart.json').read_text());pages=chart['pages']
    assert len(pages)==8 and all(len(p['patches'])==48 for p in pages)
    assert len({p['id'] for p in pages})==8
    for p in pages:
        assert len({x['id'] for x in p['patches']})==48
        assert all(len(x['rgb8_srgb'])==3 and min(x['rgb8_srgb'])>=0 and max(x['rgb8_srgb'])<=255 for x in p['patches'])
    checks['screen_pages_and_patch_counts']='8 × 48'
    html=(HERE/'screen_chart.html').read_text()
    assert 'src="http' not in html and 'fetch(' not in html and 'setInterval(' not in html
    checks['screen_self_contained_no_network_no_automatic_advance']=True
    bank=json.loads((HERE/'calibration_bank_design.json').read_text());params=bank['parameter_order']
    assert not bank['compile'] and not bank['deployable']
    for key in ['bank_A','bank_B']:
        assert [s['slot'] for s in bank[key]]==list(range(1,17))
        for slot in bank[key]:
            for name,val in slot['settings']['controls_display'].items():
                assert isinstance(val,int)
                assert (-8<=val<=8) if name.startswith('wb_') else (1<=val<=9)
    base=np.array([0 if n.startswith('wb_') else 5 for n in params])
    X=np.column_stack([np.ones(16),np.array([[s['settings']['controls_display'][n] for n in params] for s in bank['bank_A']])-base])
    assert np.array_equal(X.T@X,np.eye(16)*16)
    checks['experiment_main_effect_design_rank']=int(np.linalg.matrix_rank(X))
    # A literal two-component SOF3 fixture, predictor 1, independently calculated
    # signed differences and entropy bytes 4a16e3, not output from our encoder.
    def marker(k,b):return bytes([255,k])+struct.pack('>H',len(b)+2)+b
    fixture=b'\xff\xd8'+marker(0xc3,bytes([14,0,2,0,2,2,0,17,0,1,17,0]))
    fixture+=marker(0xc4,bytes([0,1,1,1]+[0]*13+[1,2,0]))
    fixture+=marker(0xda,bytes([2,0,0,1,0,1,0,0]))+bytes.fromhex('4a16e3')+b'\xff\xd9'
    raw,desc=decode(fixture)
    np.testing.assert_array_equal(raw,[[8193,8191,8195,8190],[8194,8192,8197,8189]])
    checks['restricted_lossless_decoder_literal_fixture']=True
    gxr=json.loads((HERE/'gxr_characterisation.json').read_text())
    assert len(gxr['pairs'])==9
    for p in gxr['pairs']:
        np.testing.assert_allclose(p['matrix']['neutral_check_xyz_d50'],[.96422,1,.82521],atol=1e-10)
        assert p['metadata_dng']['display13']==p['metadata_jpeg']['display13']
        for key in ['dng','jpeg']:
            f=Path(p[key]['path']);assert sha(f)==p[key]['sha256']
    checks['GXR_pairs_and_matrix_neutral_checks']=9
    gg=Tiff(Path(gxr['pairs'][0]['dng']['path']).read_bytes()).tags()
    rr=Tiff(Path('/tmp/gxr_color_refs/downloads/bastibe_gr3_dng/Target.DNG').read_bytes()).tags()
    b,desc=common_white_sensor_bridge(gg,rr)
    other,_=common_white_sensor_bridge({**gg,50728:[.4,1.,.8]},rr)
    np.testing.assert_array_equal(b,other)
    np.testing.assert_allclose(desc['neutral_transport_check'],[0,0,0],atol=1e-12)
    checks['common_white_bridge_neutral_transport_and_WB_invariance']=True
    prior=json.loads((ROOT/'research/color_calibration/new_captures_analysis.json').read_text())
    prior_inputs={}
    for p in prior['captures']:prior_inputs.update(p['inputs'])
    prior_inputs.update(json.loads((ROOT/'research/color_calibration/capture_analysis.json').read_text())['input'])
    for path,d in prior_inputs.items():assert sha(ROOT/path)==d['sha256']
    checks['capture_hashes_equal_prior_archived_baseline']=len(prior_inputs)
    gr=json.loads((HERE/'gr3_reference_measurements.json').read_text())
    assert gr['crop_raw_xywh']==[68,40,6000,4000]
    assert gr['variants']['positive']['metadata']['image_tone_code']==[262]
    assert gr['variants']['negative']['metadata']['image_tone_code']==[267]
    assert gr['variants']['negative']['metadata']['software'].endswith('1.71')
    checks['GR3_source_mode_version_crop_verified']=True
    manifest=json.loads((HERE/'source_manifest.json').read_text());downloads=manifest['downloads']
    for d in downloads:
        if d['status']=='downloaded':
            p=Path(d['local_path']);assert sha(p)==d['sha256'] and p.stat().st_size==d['bytes']
        elif d.get('bytes',0)>0 and d.get('partial_sha256'):
            p=Path(d['local_path']);assert sha(p)==d['partial_sha256'] and p.stat().st_size==d['bytes']
    for d in manifest['extracted_adobe_profiles']:
        p=Path(d['path_scratch']);assert sha(p)==d['sha256'] and p.stat().st_size==d['bytes']
    checks['download_hashes_verified']=sum(d['status']=='downloaded' for d in downloads)
    checks['Adobe_profile_hashes_verified']=len(manifest['extracted_adobe_profiles'])
    audit=json.loads((HERE/'package_integrity_audit.json').read_text())
    assert len(audit['packages'])==2 and all(p['all_member_digests_match'] for p in audit['packages'])
    assert all(p['native_signature_exit_code']!=0 for p in audit['packages'])
    checks['package_members_match_but_native_signatures_fail_as_reported']=True
    for package in manifest.get('assembled_packages',[]):
        path=Path(package['path_scratch'])
        assert path.stat().st_size==package['bytes'] and sha(path)==package['sha256']
    if manifest.get('assembled_packages'):checks['assembled_package_hashes_verified']=len(manifest['assembled_packages'])
    constraints=json.loads((HERE/'gr_firmware_constraints.json').read_text())
    for source in constraints['upstream_inputs']:
        assert sha(ROOT/source['path'])==source['sha256']
    matrices=[t for v in constraints['variants'] for t in v['look_matrix_constraints']]
    assert len(matrices)==9
    for t in matrices:
        assert hashlib.sha256(struct.pack('<9h',*t['values'])).hexdigest()==t['sha256']
    checks['parallel_derived_matrix_hashes_verified']=9
    refs=json.loads((HERE/'references.json').read_text())
    assert len(refs['targets'])==18 and len(refs['deferred_other_brands'])==11 and refs['golden_reference_count']==0
    assert all(t['gxr_parameters'] is None and t['gxr_best_case_residual_de00'] is None and not t['deployable'] for t in refs['targets'])
    assert all([s['rank'] for s in t['ranked_sources']]==list(range(1,len(t['ranked_sources'])+1)) for t in refs['targets'])
    checks['no_brand_recipes_or_unmeasured_residuals']=True
    assert not list(HERE.glob('*.dcp')) and not list(HERE.glob('*.cube')) and not list(HERE.glob('*.DAT'))
    checks['no_proprietary_originals_or_camera_banks_in_deliverables']=True
    # Synthetic gate tests check scoring logic only. These are NOT camera acceptance.
    temp=Path('/tmp/gxr_color_refs/verification');temp.mkdir(parents=True,exist_ok=True)
    rows=[]
    for look in ['Positive Film','Negative Film']:
        for scene in ['V1','V2','V3','V4','objects1','objects2']:
            pp=next(p['patches'] for p in pages if p['id']==scene) if scene.startswith('V') else [next(p for p in pages if p['id']=='V1')['patches'][i] for i in [4,12,22,32,33,34,38,39,40,41,42,43]]
            for rep in ['1','2','3']:
                for patch in pp:
                    rgb=srgb_decode(np.array(patch['rgb8_srgb'])/255)
                    group=patch['group']
                    if scene.startswith('objects') and patch['id'].startswith('VN'):group='neutral'
                    row={'look':look,'scene':scene,'repeat':rep,'patch_id':patch['id'],'group':group,'valid':'1'}
                    row.update({'actual_'+c:float(v) for c,v in zip('RGB',rgb)});row.update({'target_'+c:float(v) for c,v in zip('RGB',rgb)})
                    rows.append(row)
    fixture_csv=temp/'perfect_synthetic.csv'
    def write_rows(rr):
        with fixture_csv.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    reference={'golden_reference_validated':True,'renderer_sha256':'synthetic-fixture-not-camera','gr_generation':'GR III','firmware_version':'fixture',
        'look_settings':'fixture','sensor_bridge_convention':'fixture','exposure_scale_frozen':True,'common_white_frozen':True,'same_gr_pair_error':{'de00_median':0,'de00_p90':0}}
    quality={k:True for k in ['settings_frozen','raw_headroom_checked','registration_checked','repeatability_checked','no_new_channel_clipping','reference_coverage_checked']}
    quality.update(repeatability_de00_p90=0,retuned_on_acceptance=False)
    write_rows(rows);perfect=score(fixture_csv,reference,quality)
    assert perfect['status']=='PASS_DECLARED_SCREEN_ALIGNMENT',perfect['failures']
    blocked=score(fixture_csv,{**reference,'golden_reference_validated':False},quality)
    assert blocked['status']=='FAIL_OR_BLOCKED'
    blocked=score(fixture_csv,{**reference,'same_gr_pair_error':{'de00_median':None,'de00_p90':None}},quality)
    assert blocked['status']=='FAIL_OR_BLOCKED'
    wrong_ids=[dict(r) for r in rows]
    for r in wrong_ids:
        if r['scene']=='V1' and r['repeat']=='1':r['patch_id']='wrong-'+r['patch_id']
    write_rows(wrong_ids)
    assert score(fixture_csv,reference,quality)['status']=='FAIL_OR_BLOCKED'
    broken=[dict(r) for r in rows];broken[0]['actual_R']=1.;write_rows(broken)
    assert score(fixture_csv,reference,quality)['status']=='FAIL_OR_BLOCKED'
    write_rows([r for r in rows if not(r['scene']=='V1' and r['repeat']=='1')])
    assert score(fixture_csv,reference,quality)['status']=='FAIL_OR_BLOCKED'
    checks['acceptance_evaluator_synthetic_gate_tests']=['perfect fixture passes','unvalidated reference blocks','null reference errors block','changed patch IDs fail','bad colour fails','missing frame fails']
    outputs={str(p.relative_to(HERE)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='verification.json'}
    (HERE/'verification.json').write_text(json.dumps({'schema':'research-artifact-verification-v1','checks':checks,
        'actual_camera_acceptance':'NOT_RUN','golden_reference_count':0,'files':outputs},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
