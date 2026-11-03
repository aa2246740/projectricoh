"""Bind final DAT, byte derivation, cold boots, menus and page receipts."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *


def read(path):
    return json.loads(path.read_text())


def main():
    guard(create_tmp=False)
    raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();digest=sha(raw)
    frozen=read(HERE/'local/frozen-inputs.json');assert freeze()==frozen
    r1_names={'ramp.html','OWNER_STEPS_RAMP.md','FIELD_20261103.md','FIELD_20261103_BRACKET.md','FIELD_20261103_RAMP.md'}
    r1_preserved={}
    for sums in ('RAMP.SHA256SUMS','FIELD_20261103.SHA256SUMS','FIELD_20261103_BRACKET.SHA256SUMS','FIELD_20261103_RAMP.SHA256SUMS'):
        for line in (HERE.parent/'probe_pack_r1'/sums).read_text().splitlines():
            if not line:continue
            wanted,name=line.split('  ',1)
            if Path(name).name in r1_names:
                assert sha((ROOT/name).read_bytes())==wanted,name
                r1_preserved[name]=wanted
    assert {Path(name).name for name in r1_preserved}==r1_names
    selected=[]
    def receipt(relative,dat=True):
        path=HERE/relative;value=read(path)
        assert value['status']=='PASS',relative
        if dat:assert value['dat_sha256']==digest,relative
        selected.append(dict(path=relative,sha256=sha(path.read_bytes())))
        return value
    build=receipt('evidence/build.json')
    host=receipt('evidence/host.json');codec=receipt('evidence/python.json')
    independent=receipt('local/independent.json');bss=receipt('local/bss-audit.json',False)
    relink=receipt('local/evidence/relink.json',False)
    assert relink['object_inputs']==read(ROOT/'research/probe_pack_r1/local/evidence/relink.json')['object_inputs']
    assert all(sha(Path(path).read_bytes())==wanted for path,wanted in relink['object_inputs'].items())
    assert len(independent['complete_552'])==independent['host_outputs_checked']==15
    assert len(independent['preserved_native'])==21 and independent['prior_JQ_and_M_A_equal']
    assert bss['all_GOTOFF_relocations']==774 and bss['BSS_relocations_by_kind']=={'63':289,'64':289}
    assert bss['all_changes_BSS_only'] and bss['translation_equal'] and bss['all_symbols_in_allocation']
    assert len(host['complete_outputs'])==15 and host['builtin_titles_valid']==24
    assert host['every_glyph_reused_from_native_or_prior_probe'] and not host['novel_characters']
    assert len(host['rejected_crc_cases'])==9 and host['window_cases']==61250
    assert codec['records']==48 and codec['codec_byte_roundtrip']
    sizes=build['sizes']
    for key,limit in [('file_bytes','file_limit'),('code_bytes','code_limit'),('main_request','main_limit')]:
        assert sizes[key]<=sizes[limit]
    assert bss['main_bytes']==sizes['main_request']
    assert sizes['file_bytes']==len(raw) and build['source_C_unchanged']
    assert build['P1_nodes']==[16] and build['P1_delta']==-2
    assert build['P2_nodes']==[8,19] and build['P2_delta']==2
    assert build['v39_only'] and not build['v310_compatible'] and not build['c120_included']
    restart_inputs=receipt('evidence/restart-inputs.json')
    assert sum(r['equivalent_sources'] for r in restart_inputs['cases'])==15
    expected=read(HERE/'local/expected.json');layout=read(ROOT/'research/g154_looks_r1/layout.json')
    units=[];foreign_total=0;close_total=0
    for unit,prefix,label,closes,foreign in [('mount','m','M',13,8),('50mm','j','J',7,11),('28mm','q','Q',7,11)]:
        def cold_checks(name,restart=False):
            folder=HERE/'local/cold'/name
            cold=read(folder/'cold.json');detail=read(folder/'detail.json');snap=read(folder/'snapshot.json')
            assert cold['error'] is None and cold['cold_origin'] and cold['start_step']==0
            assert cold['image_sha256']==BODY_SHA and cold['unit_model']==unit
            assert [r['state'] for r in cold['state_sequence']]==[0,2,32,5]
            assert cold['batch'] and cold['batch_stats']['batch-steps']>0 and cold['nice']>=10
            assert detail['native_state_presets']==snap['native_state_presets']==[]
            assert detail['dat_sha256']==digest and snap['media']['files']['GXRCE.DAT']==digest
            assert sha((folder/'standby.snap.z').read_bytes())==snap['sha256']
            if restart:
                source=(HERE/'local/restart-inputs'/(unit+'.bin')).read_bytes()
                assert (folder/'cold-S.bin').read_bytes()==source
                assert detail['settings_source_sha256']==sha(source)
                assert detail['settings_source_reads'] and all(r['source_sha256']==sha(source) for r in detail['settings_source_reads'])
            return dict(name=name,seconds=cold['seconds'],steps=cold['steps'],snapshot_sha256=snap['sha256'])
        cold=cold_checks(prefix+'-final-cold')
        result=receipt('local/native/'+prefix+'-final-owner-c/result.json')
        assert result['backend']=='c' and result['error'] is None and result['native_state_presets']==[]
        assert result['snapshot_sha256']==cold['snapshot_sha256']
        assert len(result['foreign_effects'])==foreign and all(r['rejected'] and r['unit_writes']==0 and r['S_unchanged'] for r in result['foreign_effects'])
        assert len(result['owner_closes'])==closes and all(r['S_equal_MAIN'] and r['record_zero'] for r in result['owner_closes'])
        assert len(result['views'])==4 and {r['screen'] for r in result['views']}=={0,1,2,3}
        assert all(r['rows']==8 and r['failed']==0 for r in result['frames']+result['views'])
        assert sizes['main_request'] in result['main_allocation_requests']
        for frame,row in enumerate(result['owner_closes'],start=2):
            entry=bytes.fromhex(expected[label][row['channel']]['entry_hex'])
            wanted=b''.join(entry[o:o+n] for o,n,_ in CRC_FIELDS)+bytes(2)
            actual=HERE/'local/native'/(prefix+'-final-owner-c')/(str(frame)+'-'+row['channel']+'.bin')
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
            name=prefix+'-'+kind+'-final-c'
            negative=receipt('local/native/'+name+'/result.json',False)
            assert negative['dat_sha256']==sha((HERE/'local/host'/(kind+'.DAT')).read_bytes())
            assert negative['backend']=='c' and negative['rejected_input'] and negative['error'] is None
            assert negative['native_state_presets']==[]
            assert not [r for r in negative['native_log'] if r.get('op')=='rpc' and r.get('cmd')==22]
            logs=[json.loads(line) for line in (HERE/'local/runlogs'/(name+'.log')).read_text().splitlines() if line.startswith('{')]
            rejected=[r for r in logs if r.get('phase')=='rejected']
            assert len(rejected)==1 and rejected[0]['rows']==7 and rejected[0]['unit_writes']==0
        units.append(dict(unit=unit,cold=cold,restart=restarted,owner_close_reopens=closes,
            foreign_rejections=foreign,owned_views=4,physical_rows=8,restart_pure04=True))
        foreign_total+=foreign;close_total+=closes
    c=receipt('local/unit/unit-final-c/result.json');py=receipt('local/unit/unit-final-python/result.json')
    assert c['backend']=='c' and py['backend']=='python' and c['units']==py['units']
    official_calls=sum(len(r['sequence']) for r in c['units']);assert official_calls==27
    mount=read(HERE/'local/native/m-final-owner-c/result.json')
    py=receipt('local/native/m-final-owner-python/result.json')
    assert py['backend']=='python'
    for key in ('frames','views','foreign_effects','owner_closes','diagnostics'):
        assert py[key]==mount[key],key
    for name,count in [('negative',9),('restart-native',3),('unit',2)]:
        record=receipt('evidence/'+name+'.json');assert len(record['jobs'])==count
        assert all(r['returncode']==0 for r in record['jobs'])
    reproduced=receipt('evidence/reproduce.json',False)
    for item in reproduced['files']:
        path=PACKAGE/'local'/item['file'];assert sha(path.read_bytes())==item['sha256']
    packaged=receipt('evidence/package.json')
    assert packaged['archive_sha256']==sha((PACKAGE/'local/GXR-probe2.zip').read_bytes())
    assert packaged['photo_count']==13 and packaged['P2_nodes']==[8,19]
    page=read(HERE/'local/page/check.json');pixels=read(HERE/'local/pixels.json')
    page_sha=sha((HERE/'ramp2.html').read_bytes())
    assert page['status']==pixels['status']=='PASS'
    assert page['htmlSha256']==pixels['htmlSha256']==page_sha
    assert len(page['cases'])==len(pixels['cases'])==18
    assert page['networkRequests']==page['errors']==[] and page['closedNormally'] and page['phaseGeometryUnchanged']
    assert pixels['marker_minimum_hamming_distance']>=4
    plan=read(HERE/'local/page-plan.json')
    assert plan['status']=='PASS_PREDICTION_ONLY' and plan['nominal_ok'] and plan['sensitivity_ok']
    assert plan['P1_node']==16 and plan['P2_nodes']==[8,19] and abs(plan['exposure_s']-1/15)<1e-12
    for path,digest_input in plan['source_files'].items():assert sha((ROOT/path).read_bytes())==digest_input
    for phase in ('p1','p2'):
        page_plan=plan['pages'][phase]
        assert len(page_plan['codes'])==49 and len(page_plan['colors'])==3
        assert len({r['transfer'] for r in page_plan['coverage']})==4
        assert all(r['left_points']>=2 and r['right_points']>=2 and r['below_support'] and r['above_support'] for r in page_plan['coverage'])
    result=dict(status='PASS',gate='可以交复审',tested_layer='host and declared emulator models',dat_sha256=digest,
        body_sha256=BODY_SHA,units=units,complete_552=15,preserved_native_552=21,all_GOTOFF_relocations=774,
        foreign_rejections=foreign_total,native_crc_rejections=9,owner_close_reopens=close_total,
        official_packer_calls_each_backend=official_calls,mount_native_Python_matches_C=True,
        C_nonPASS_cases=0,native_UI_state_presets=False,protected_inputs=len(frozen),source_C_unchanged=True,
        sealed_r1_public_files_unchanged=r1_preserved,
        page_cases=18,uniform_sample_regions=936,corner_decodes=72,page_sha256=page_sha,
        sizes=sizes,photos=13,owner_unit='MOUNT',v39_only=True,v310_compatible=False,
        full_GPIO_font_LCD='OPEN: inherited provisional NAND font geometry model boundary',
        physical_card_NAND_power_loss='UNRUN',new_chart_RAW_coverage='PREDICTED: verify next A RAW',
        selected_receipts=selected)
    save(HERE/'evidence/acceptance.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('selected_receipts','units')},ensure_ascii=False))


if __name__=='__main__':main()
