"""Check the independent review receipts before allowing a card-gate verdict."""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_review import ROOT,REVIEW,LOCAL,SOURCE,PACKAGE,sha,save,setup,load

def read(path):return json.loads(path.read_text())

def passed(path):
    value=read(path);assert value['status']=='PASS',str(path)
    return value

def main():
    setup()
    raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();digest=sha(raw)
    static=passed(LOCAL/'static-audit.json')
    rebuilt=passed(LOCAL/'rebuild-comparison.json')
    host=passed(REVIEW/'evidence/host.json')
    codec=passed(REVIEW/'evidence/python.json')
    response=passed(REVIEW/'evidence/response.json')
    rpc=passed(LOCAL/'rpc-whitelist.json')
    assert all(value['dat_sha256']==digest for value in (static,host,codec,response,rpc))
    assert static['complete_DAT_reconstruction'] and static['changed_code_words']==289
    assert static['all_changed_words_low16_minus32'] and static['unchanged_link_inputs']==28
    assert static['current_engine_sources_equal_probe2_freeze']==89
    assert len(static['complete_552'])==15 and len(static['preserved_native'])==21
    assert len(rebuilt['matches'])==4 and len(host['complete_outputs'])==15
    for row in static['complete_552']:
        assert (LOCAL/'host'/f"{row['unit']}-{row['key']}.bin").read_bytes()==(LOCAL/'independent'/f"{row['unit']}-{row['key']}.bin").read_bytes()
    assert len(host['rejected_crc_cases'])==9 and host['window_cases']==61250
    assert codec['records']==48 and codec['codec_byte_roundtrip']
    expected=read(LOCAL/'expected.json');layout=read(ROOT/'research/g154_looks_r1/layout.json')
    fmt=load(REVIEW/'static_review.py','probe3_review_independent_parser')
    units=[]
    for unit,prefix,label,name,closes,foreign in [('mount','m','M','mount-owner-c',8,8),('50mm','j','J','j-owner-c',7,11),('28mm','q','Q','q-owner-c',7,11)]:
        result=passed(LOCAL/'native'/name/'result.json')
        assert result['backend']=='c' and result['error'] is None and result['dat_sha256']==digest
        assert result['native_state_presets']==[]
        assert len(result['foreign_effects'])==foreign and all(r['rejected'] and r['unit_writes']==0 and r['S_unchanged'] for r in result['foreign_effects'])
        assert len(result['owner_closes'])==closes and all(r['S_equal_MAIN'] and r['record_zero'] for r in result['owner_closes'])
        assert len(result['views'])==4 and {r['screen'] for r in result['views']}=={0,1,2,3}
        assert all(r['rows']==8 and r['failed']==0 for r in result['frames']+result['views'])
        assert 100160 in result['main_allocation_requests']
        cold=SOURCE/'local/cold'/(prefix+'-final-cold')
        origin=read(cold/'cold.json');meta=read(cold/'snapshot.json')
        assert origin['start_step']==0 and origin['cold_origin'] and origin['image_sha256']=='8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d'
        assert [r['state'] for r in origin['state_sequence']]==[0,2,32,5]
        assert meta['media']['files']['GXRCE.DAT']==digest and meta['native_state_presets']==[]
        assert result['snapshot_sha256']==meta['sha256']==sha((cold/'standby.snap.z').read_bytes())
        for number,row in enumerate(result['owner_closes'],2):
            entry=bytes.fromhex(expected[label][row['channel']]['entry_hex'])
            wanted=b''.join(entry[o:o+n] for o,n,_ in fmt.FIELDS)+bytes(2)
            assert (LOCAL/'native'/name/(str(number)+'-'+row['channel']+'.bin')).read_bytes()==wanted
        g=(LOCAL/'native'/name/'g.bin').read_bytes()
        assert g[layout['g.live']:layout['g.live']+552]==fmt.expand(raw,dict(mount=2,**{'50mm':0,'28mm':1})[unit],4)
        restarted=passed(LOCAL/'native'/(prefix+'-restart-open-c')/'result.json')
        assert restarted['initial_only'] and restarted['error'] is None and len(restarted['frames'])==1
        assert restarted['frames'][0]['cur']==3 and restarted['frames'][0]['slot']==4
        g=(LOCAL/'native'/(prefix+'-restart-open-c')/'g.bin').read_bytes()
        assert g[layout['g.live']:layout['g.live']+552]==fmt.expand(raw,dict(mount=2,**{'50mm':0,'28mm':1})[unit],4)
        for kind in ('header-crc','payload-crc','effect-crc'):
            negative=passed(LOCAL/'native'/(prefix+'-'+kind+'-c')/'result.json')
            assert negative['rejected_input'] and negative['error'] is None
            assert not [r for r in negative['native_log'] if r.get('op')=='rpc' and r.get('cmd')==22]
            log=(LOCAL/(prefix+'-'+kind+'-c.log')).read_text()
            rejected=[json.loads(line) for line in log.splitlines() if line.startswith('{') and json.loads(line).get('phase')=='rejected']
            assert len(rejected)==1 and rejected[0]['rows']==7 and rejected[0]['unit_writes']==0
        units.append(dict(unit=unit,owner_steps=closes,foreign_rejections=foreign,owned_views=4,
            source_MAIN_snapshot=meta['sha256'],source_MAIN_rerun=False,restart_pure04=True))
    restart=passed(LOCAL/'restart-source-review.json')
    assert sum(len(row['independent_post_B_inputs']) for row in restart['cases'])==12
    restored=passed(LOCAL/'native/mount-G154L-open-c/result.json')
    assert restored['initial_only'] and restored['error'] is None and 103644 in restored['main_allocation_requests']
    base=(ROOT/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert restored['dat_sha256']==sha(base)
    g=(LOCAL/'native/mount-G154L-open-c/g.bin').read_bytes()
    assert g[layout['g.live']:layout['g.live']+552]==fmt.expand(base,2,4)
    mount=passed(LOCAL/'native/mount-owner-c/result.json')
    reference=passed(LOCAL/'native/mount-owner-python/result.json')
    comparison=[]
    for key in ('frames','views','foreign_effects','owner_closes','diagnostics','native_log','calls','watch','transitions','main_allocation_requests'):
        assert reference[key]==mount[key],key
        comparison.append(key)
    cunit=passed(LOCAL/'unit/unit-review-c/result.json');punit=passed(LOCAL/'unit/unit-review-python/result.json')
    assert cunit['units']==punit['units']
    assert sum(len(row['sequence']) for row in cunit['units'])==27
    page=passed(LOCAL/'page/check.json');pixels=passed(LOCAL/'pixels.json')
    pagehash=sha((SOURCE/'ramp3.html').read_bytes())
    assert page['htmlSha256']==pixels['htmlSha256']==pagehash
    assert len(page['cases'])==len(pixels['cases'])==80 and page['closedNormally']
    assert not page['networkRequests'] and not page['errors']
    assert pixels['label_only_changes'] and pixels['frame_total_RGB_constant'] and pixels['measured_surroundings_pixel_identical']
    assert pixels['marker_minimum_hamming_distance']>=4 and pixels['viewport_groups']==10
    assert response['candidate_classes']==7 and response['real_frames']==10
    assert response['missing_and_stale_labels_do_not_change_response'] and response['deliberate_conflicts_retained']
    assert sha((LOCAL/'response-checks-detail.json').read_bytes())==response['detail_sha256']
    boundary=[read(LOCAL/('boundary-'+backend+'.json')) for backend in ('c','python')]
    assert all(row['status']=='OBSERVED' and row['root_image']==0 for row in boundary)
    assert boundary[0]['reason']==boundary[1]['reason']=='fault'
    assert boundary[0]['detail']==boundary[1]['detail']=='NAND read exceeds provisional page geometry'
    assert boundary[0]['pc']==boundary[1]['pc']
    steps=(SOURCE/'OWNER_STEPS_PROBE3.md').read_text()
    names=[re.search(r'`([^`]+)`',line).group(1) for line in steps.splitlines() if re.match(r'\| \d+ \|',line)]
    assert names==['M26 A','P1 R+2','P1 R-2','P1 G+2','P1 G-2','P1 B+2','P1 B-2','M26 A']
    jobs=read(LOCAL/'suite-jobs.json');assert len(jobs)==19 and all(r['returncode']==0 for r in jobs)
    result=dict(status='PASS_WITH_DEVICE_BOUNDARIES',dat_sha256=digest,
        zip_sha256=sha((PACKAGE/'local/GXR-probe3.zip').read_bytes()),units=units,
        mount_C_Python_identical_fields=comparison,official_packer_calls_per_backend=27,
        complete_552_independent_and_C_equal=15,preserved_native_552=21,
        RPC_halfword_writes=sum(r['row_write_halfwords'] for r in rpc['cases']),
        unchanged_RPC_neighbour_bytes=sum(r['unchanged_neighbour_checks'] for r in rpc['cases']),
        native_CRC_rejections=9,cross_unit_rejections=30,physical_rows=8,
        screenshots=80,constant_pixel_sample_regions=4160,decoded_markers=320,
        prior_real_response_frames=10,GPIO_NAND_boundary='C and Python retained-state instruction replay only',
        target_card_hash_check='Required from helper; this review never reads a card',
        owner_order=names)
    save(LOCAL/'acceptance-review.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
