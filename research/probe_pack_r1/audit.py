"""Bind the selected completed receipts to the final packaged artifact."""
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
    assert freeze()==read(HERE/'local/frozen-inputs.json')
    host=read(HERE/'evidence/host.json')
    assert host['status']=='PASS' and host['dat_sha256']==digest
    assert len(host['complete_outputs'])==12 and host['builtin_titles_valid']==24
    assert len(host['rejected_crc_cases'])==9 and host['window_cases']==61250
    units=[]
    selected=[]
    for unit,prefix in (('mount','m'),('50mm','j'),('28mm','q')):
        case=HERE/'local/native'/(prefix+'-owner-c-final')/'result.json'
        result=read(case)
        assert result['status']=='PASS' and result['dat_sha256']==digest and result['error'] is None
        assert result['backend']=='c' and result['native_state_presets']==[]
        assert len(result['foreign_effects'])==8 and all(r['rejected'] and r['unit_writes']==0 and r['S_unchanged'] for r in result['foreign_effects'])
        assert len(result['owner_closes'])==7 and all(r['S_equal_MAIN'] and r['record_zero'] for r in result['owner_closes'])
        assert len(result['views'])==4 and all(r['rows']==8 for r in result['frames']+result['views'])
        assert set(r['screen'] for r in result['views'])=={0,1,2,3}
        assert 100032 in result['main_allocation_requests']
        selected.append(str(case.relative_to(HERE)))
        cold=read(HERE/'local/cold'/(prefix+'-final-cold-r1')/'cold.json')
        assert cold['error'] is None and cold['cold_origin'] and cold['start_step']==0
        assert [s['state'] for s in cold['state_sequence']]==[0,2,32,5]
        assert cold['batch'] and cold['batch_stats']['batch-steps']>0 and cold['nice']>=10
        restart_name=prefix+('-restart-r2' if prefix=='m' else '-restart-r1')
        restart=read(HERE/'local/cold'/restart_name/'detail.json')
        original=(HERE/'local/restart-inputs'/(unit+'.bin')).read_bytes()
        after=(HERE/'local/cold'/restart_name/'cold-S.bin').read_bytes()
        assert after==original and restart['settings_source_sha256']==sha(original)
        assert restart['settings_source_reads'] and restart['native_state_presets']==[]
        check=read(HERE/'local/native'/(prefix+'-restart-native-c')/'result.json')
        assert check['status']=='PASS' and check['initial_only'] and check['dat_sha256']==digest
        assert check['frames'][0]['cur']==3 and check['frames'][0]['rows']==8
        selected.append(str((HERE/'local/native'/(prefix+'-restart-native-c')/'result.json').relative_to(HERE)))
        refusals=[]
        for kind in ('header-crc','payload-crc','effect-crc'):
            name=prefix+'-'+kind+'-c'
            negative=read(HERE/'local/native'/name/'result.json')
            assert negative['status']=='PASS' and negative['rejected_input'] and negative['error'] is None
            assert not [r for r in negative['native_log'] if r.get('op')=='rpc' and r.get('cmd')==22]
            refusals.append(name);selected.append('local/native/'+name+'/result.json')
        units.append(dict(unit=unit,owner_seconds=result['seconds'],owned_views=4,foreign_rejections=8,
                          owner_close_reopen_steps=7,pure04_after_restart=True,
                          persisted_4096_read_identical=True,crc_rejections=refusals))
    python=read(HERE/'local/native/mount-owner-python-final/result.json')
    mount=read(HERE/'local/native/m-owner-c-final/result.json')
    assert python['status']=='PASS' and python['backend']=='python' and python['dat_sha256']==digest
    assert python['frames']==mount['frames'] and python['views']==mount['views']
    selected.append('local/native/mount-owner-python-final/result.json')
    cc=read(HERE/'local/unit/unit-c-final/result.json')
    py=read(HERE/'local/unit/unit-python-final/result.json')
    assert cc['status']==py['status']=='PASS' and cc['dat_sha256']==py['dat_sha256']==digest
    assert cc['units']==py['units']
    c120c=read(HERE/'local/c120/mount-native-c-r1/result.json')
    c120p=read(HERE/'local/c120/mount-native-python-r1/result.json')
    assert c120c['status']==c120p['status']=='PASS' and c120c['records']==c120p['records']
    assert [r['gain4'] for r in c120c['records']]==[64,64,60,64]
    page=read(HERE/'evidence/page.json')
    assert page['status']=='PASS' and page['htmlSha256']==sha((HERE/'patches.html').read_bytes())
    assert page['c120Patches']==18 and page['type26Patches']==6 and page['networkRequests']==0
    codec=read(HERE/'evidence/python.json')
    assert codec['status']=='PASS' and codec['final_dat_sha256']==digest and codec['studio_byte_round_trip']
    result=dict(status='PASS',dat_sha256=digest,body_sha256=BODY_SHA,units=units,
        complete_552_outputs=12,production_C_window_cases=61250,builtin_titles=24,
        foreign_engine_rejections=24,native_crc_rejections=9,unit_mirror_sequences_each_backend=21,
        mount_owner_Python_matches_C=True,C120_mapping_and_isolated_loader=True,C120_DAT_included=False,
        C120_trigger_and_completion_lifecycle='OPEN',full_GPIO_menu='OPEN: NAND font model boundary',
        native_UI_state_presets=False,source_C_unchanged=True,protected_inputs=len(freeze()),
        photos=13,owner_unit='MOUNT',selected_receipts=selected)
    save(HERE/'evidence/acceptance.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
