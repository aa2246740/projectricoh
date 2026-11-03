"""Bind all acceptance evidence to the final probe3 DAT and single eight-shot page."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def read(path):return json.loads(path.read_text())


def main():
    guard(create_tmp=False);raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();digest=sha(raw)
    frozen=read(HERE/'local/frozen-inputs.json');assert freeze()==frozen
    selected=[]
    def receipt(relative,dat=True):
        path=HERE/relative;value=read(path);assert value['status']=='PASS',relative
        if dat:assert value['dat_sha256']==digest,relative
        selected.append(dict(path=relative,sha256=sha(path.read_bytes())))
        return value
    build=receipt('evidence/build.json');host=receipt('evidence/host.json');codec=receipt('evidence/python.json')
    independent=receipt('local/independent.json');bss=receipt('local/bss-audit.json',False)
    relink=receipt('local/evidence/relink.json',False)
    assert relink['object_inputs']==read(ROOT/'research/probe_pack_r2/local/evidence/relink.json')['object_inputs']
    assert all(sha(Path(p).read_bytes())==wanted for p,wanted in relink['object_inputs'].items())
    assert len(independent['complete_552'])==independent['host_outputs_checked']==15
    assert len(independent['preserved_native'])==21 and independent['prior_JQ_and_M_A_equal']
    assert independent['probe2_negative16_complete_552_equal']==3
    assert independent['probe2_first12_descriptors_byte_equal'] and independent['probe2_all_native_records_equal']
    assert independent['original_positive16_complete_552_equal']==3
    assert bss['all_GOTOFF_relocations']==774 and bss['BSS_relocations_by_kind']=={'63':289,'64':289}
    assert bss['all_changes_BSS_only'] and bss['translation_equal'] and bss['all_symbols_in_allocation']
    assert len(host['complete_outputs'])==15 and host['builtin_titles_valid']==24
    assert host['every_glyph_reused_from_native_or_prior_probe'] and not host['novel_characters']
    assert len(host['rejected_crc_cases'])==9 and host['window_cases']==61250
    assert codec['records']==48 and codec['codec_byte_roundtrip']
    sizes=build['sizes']
    for used,limit in [('file_bytes','file_limit'),('code_bytes','code_limit'),('main_request','main_limit')]:
        assert sizes[used]<=sizes[limit]
    assert bss['main_bytes']==sizes['main_request'] and sizes['file_bytes']==len(raw)
    assert build['source_C_unchanged'] and build['node']==16 and build['negative_delta']==-2 and build['positive_delta']==2
    assert build['photo_count']==8 and not build['optional_set']
    assert build['v39_only'] and not build['v310_compatible'] and not build['c120_included']
    restart_inputs=receipt('evidence/restart-inputs.json')
    assert sum(v['equivalent_sources'] for v in restart_inputs['cases'])==12
    expected=read(HERE/'local/expected.json');layout=read(ROOT/'research/g154_looks_r1/layout.json');units=[]
    for unit,prefix,label,closes,foreign in [('mount','m','M',8,8),('50mm','j','J',7,11),('28mm','q','Q',7,11)]:
        def cold_checks(name,restart=False):
            folder=HERE/'local/cold'/name
            cold=read(folder/'cold.json');detail=read(folder/'detail.json');snap=read(folder/'snapshot.json')
            assert cold['error'] is None and cold['cold_origin'] and cold['start_step']==0
            assert cold['image_sha256']==BODY_SHA and cold['unit_model']==unit
            assert [v['state'] for v in cold['state_sequence']]==[0,2,32,5]
            assert cold['batch'] and cold['batch_stats']['batch-steps']>0 and cold['nice']>=15
            assert detail['native_state_presets']==snap['native_state_presets']==[]
            assert detail['dat_sha256']==digest and snap['media']['files']['GXRCE.DAT']==digest
            assert sha((folder/'standby.snap.z').read_bytes())==snap['sha256']
            if restart:
                source=(HERE/'local/restart-inputs'/(unit+'.bin')).read_bytes()
                assert (folder/'cold-S.bin').read_bytes()==source and detail['settings_source_sha256']==sha(source)
                assert detail['settings_source_reads'] and all(v['source_sha256']==sha(source) for v in detail['settings_source_reads'])
            return dict(name=name,seconds=cold['seconds'],steps=cold['steps'],snapshot_sha256=snap['sha256'])
        cold=cold_checks(prefix+'-final-cold')
        path='local/native/'+prefix+'-final-owner-c/result.json';result=receipt(path)
        assert result['backend']=='c' and result['error'] is None and result['native_state_presets']==[]
        assert result['snapshot_sha256']==cold['snapshot_sha256']
        assert len(result['foreign_effects'])==foreign and all(v['rejected'] and v['unit_writes']==0 and v['S_unchanged'] for v in result['foreign_effects'])
        assert len(result['owner_closes'])==closes and all(v['S_equal_MAIN'] and v['record_zero'] for v in result['owner_closes'])
        assert len(result['views'])==4 and {v['screen'] for v in result['views']}=={0,1,2,3}
        assert all(v['rows']==8 and v['failed']==0 for v in result['frames']+result['views'])
        assert sizes['main_request'] in result['main_allocation_requests']
        for number,row in enumerate(result['owner_closes'],start=2):
            entry=bytes.fromhex(expected[label][row['channel']]['entry_hex'])
            wanted=b''.join(entry[o:o+n] for o,n,_ in CRC_FIELDS)+bytes(2)
            actual=HERE/'local/native'/(prefix+'-final-owner-c')/(str(number)+'-'+row['channel']+'.bin')
            assert actual.read_bytes()==wanted
        g=(HERE/'local/native'/(prefix+'-final-owner-c')/'g.bin').read_bytes()
        assert g[layout['g.live']:layout['g.live']+552]==expand(raw,{'50mm':0,'28mm':1,'mount':2}[unit],4)
        restarted=cold_checks(prefix+'-restart-final',True)
        check=receipt('local/native/'+prefix+'-restart-native-final-c/result.json')
        assert check['backend']=='c' and check['initial_only'] and check['error'] is None
        assert check['native_state_presets']==[] and check['snapshot_sha256']==restarted['snapshot_sha256']
        assert len(check['frames'])==1 and check['frames'][0]['cur']==3 and check['frames'][0]['slot']==4
        assert check['frames'][0]['rows']==8 and check['frames'][0]['applied_user']==0
        g=(HERE/'local/native'/(prefix+'-restart-native-final-c')/'g.bin').read_bytes()
        assert g[layout['g.live']:layout['g.live']+552]==expand(raw,{'50mm':0,'28mm':1,'mount':2}[unit],4)
        for kind in ('header-crc','payload-crc','effect-crc'):
            name=prefix+'-'+kind+'-final-c';negative=receipt('local/native/'+name+'/result.json',False)
            assert negative['dat_sha256']==sha((HERE/'local/host'/(kind+'.DAT')).read_bytes())
            assert negative['backend']=='c' and negative['rejected_input'] and negative['error'] is None
            assert negative['native_state_presets']==[]
            assert not [v for v in negative['native_log'] if v.get('op')=='rpc' and v.get('cmd')==22]
            logs=[json.loads(line) for line in (HERE/'local/runlogs'/(name+'.log')).read_text().splitlines() if line.startswith('{')]
            rejected=[v for v in logs if v.get('phase')=='rejected']
            assert len(rejected)==1 and rejected[0]['rows']==7 and rejected[0]['unit_writes']==0
        units.append(dict(unit=unit,cold=cold,restart=restarted,owner_close_reopens=closes,
            foreign_rejections=foreign,owned_views=4,physical_rows=8,restart_pure04=True))
    c=receipt('local/unit/unit-final-c/result.json');py=receipt('local/unit/unit-final-python/result.json')
    assert c['backend']=='c' and py['backend']=='python' and c['units']==py['units']
    official_calls=sum(len(v['sequence']) for v in c['units']);assert official_calls==27
    mount=read(HERE/'local/native/m-final-owner-c/result.json');py=receipt('local/native/m-final-owner-python/result.json')
    assert py['backend']=='python'
    for key in ('frames','views','foreign_effects','owner_closes','diagnostics'):assert py[key]==mount[key],key
    for name,count in [('negative',9),('restart-native',3),('unit',2)]:
        record=receipt('evidence/'+name+'.json');assert len(record['jobs'])==count and all(v['returncode']==0 for v in record['jobs'])
    reproduced=receipt('evidence/reproduce.json',False)
    for item in reproduced['files']:assert sha((PACKAGE/'local'/item['file']).read_bytes())==item['sha256']
    packaged=receipt('evidence/package.json')
    assert packaged['archive_sha256']==sha((PACKAGE/'local/GXR-probe3.zip').read_bytes())
    assert packaged['photo_count']==8 and packaged['node']==16 and not packaged['optional_set']
    page=receipt('local/page/check.json',False);pixels=receipt('local/pixels.json',False)
    page_sha=sha((HERE/'ramp3.html').read_bytes())
    assert page['htmlSha256']==pixels['htmlSha256']==page_sha
    assert len(page['cases'])==len(pixels['cases'])==80 and page['steps']==8 and page['phaseCount']==1
    assert not page['networkRequests'] and not page['errors'] and page['closedNormally']
    assert page['P1_stimulus_byte_values_unchanged'] and page['frameGeometryUnchanged']
    assert pixels['label_only_changes'] and pixels['frame_total_RGB_constant'] and pixels['measured_surroundings_pixel_identical']
    assert pixels['marker_minimum_hamming_distance']>=4 and pixels['viewport_groups']==10
    response=receipt('evidence/response.json')
    assert response['candidate_classes']==7 and response['real_frames']==10
    assert response['missing_and_stale_labels_do_not_change_response'] and response['deliberate_conflicts_retained']
    assert sha((HERE/'local/response-checks-detail.json').read_bytes())==response['detail_sha256']
    serial=receipt('evidence/serial-jobs.json');assert all(v['returncode']==0 for v in serial['jobs'])
    result=dict(status='PASS',gate='可以交复审',tested_layer='host and declared emulator models',dat_sha256=digest,
        body_sha256=BODY_SHA,units=units,complete_552=15,preserved_native_552=21,all_GOTOFF_relocations=774,
        foreign_rejections=30,native_crc_rejections=9,owner_close_reopens=22,official_packer_calls_each_backend=27,
        mount_native_Python_matches_C=True,C_nonPASS_cases=0,native_UI_state_presets=False,
        protected_inputs=len(frozen),source_C_unchanged=True,page_cases=80,uniform_sample_regions=4160,
        corner_decodes=320,page_sha256=page_sha,label_surroundings_identical=True,real_response_identity_checks=10,
        sizes=sizes,photos=8,optional_set=False,owner_unit='MOUNT',v39_only=True,v310_compatible=False,
        full_GPIO_font_LCD='OPEN: inherited provisional NAND font geometry model boundary',
        physical_card_NAND_power_loss='UNRUN',new_chart_RAW_coverage='VERIFY FROM NEW A RAW',selected_receipts=selected)
    save(HERE/'evidence/acceptance.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('selected_receipts','units')},ensure_ascii=False))


if __name__=='__main__':main()
