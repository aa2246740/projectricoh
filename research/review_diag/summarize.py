"""Check retained case records, count counterexamples, and summarize provenance."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import shlex

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]


def read(path):
    return json.loads(path.read_text())


def checked(paths, count):
    assert len(paths)==count,(len(paths),count)
    for path in paths:
        d=read(path)
        assert d['status']=='PASS',(path,d.get('error'))
        a=d['audit']
        assert a['dat_sha256']=='38e3db6eacaf05a4ad8dbafbda608e3b5695485110014f7816f32d315b3f49a1',path
        assert a['elf_sha256']=='6ed1ab8e59d44538f14c2523ab0bdc63ae023658aeeb3f6b0685dd5d2a50220a',path
        assert a['rpc8_calls']==a['file_api_calls']==a['queue2_sends']==0,path
        assert not a['unapproved_writes'] and not a['native_setters'] and not a['host_ui_writes'],path
        assert all(x['rows']==8 for x in a['ui_entries']),path
        assert not a.get('review_invalid_DAT_row_stores') and not a.get('review_boot_host_UI_presets'),path
    return paths


def main():
    basic=[]
    basic+=checked(sorted((OUT/'local/functional').glob('*.json')),3)
    basic+=checked(sorted((OUT/'local/cutpoints').glob('*.json')),264)
    basic+=checked(sorted((OUT/'local/h01').glob('*.json')),120)
    basic+=checked(sorted((OUT/'local/variants').glob('*.json')),24)
    errors=checked(sorted((OUT/'local/errors').glob('*.json')),291)
    preserve=checked(sorted((OUT/'local/probes').glob('*-preserve.json')),3)
    probes=[]
    for pattern,count in (('*-prepublish-*.json',72),('*-reopen-*.json',24),('*-withdrawal-*.json',72)):
        paths=sorted((OUT/'local/probes').glob(pattern))
        assert len(paths)==count,(pattern,len(paths))
        for path in paths:
            d=read(path)
            assert d['status']=='OBSERVED',(path,d.get('error'))
            assert d['injection']['psw']&0x40,path
            assert d['injection']['before']['rows']==7,path
        probes+=paths
    counterexamples=[]
    for path in probes:
        d=read(path)
        a=d['audit']
        assert a['rpc8_calls']==a['file_api_calls']==a['queue2_sends']==0,path
        if a['native_setters']:
            before=d['injection']['before']
            after=d['injection']['after_injection']
            counterexamples.append(dict(case=d['case'],file=str(path.relative_to(ROOT)),
                phase='withdrawal' if 'withdrawal' in d['case'] else 'prepublication',
                unit=d['unit'],key=d['key'],cut=d['cut'],psw=d['injection']['psw'],
                rows=before['rows'],inflight=before['root']['inflight'],
                mode_before=before['mode'],mode_after=after['mode'],
                settings_changed=not a['settings_unchanged'],setter_hits=len(a['native_setters'])))
    assert len(counterexamples)==56,len(counterexamples)
    assert Counter(x['phase'] for x in counterexamples)=={'prepublication':32,'withdrawal':24}
    assert sum(x['settings_changed'] for x in counterexamples)==44
    first=read(OUT/'local/probes/50mm-first-service-failure.json')
    assert first['injected'] and first['after']['opens']==1 and first['after']['rows']==7
    assert any('ig_menu' in e['names'] for e in first['audit']['entries'])
    assert first['audit']['service_counts']=={'11:2':1}
    assert read(OUT/'evidence/rebuild.json')['status']=='PASS'
    assert read(OUT/'evidence/static-audit.json')['status']=='PASS_DAT_INTRINSIC_STATIC_BOUNDARY'
    for unit in ('50mm','28mm','mount'):
        assert read(OUT/'evidence'/f'errors-{unit}.json')['status']=='PASS'
    for name,count in (('input',14022),('card',30)):
        lines=(OUT/'local'/f'{name}-sha256-check.log').read_text().splitlines()
        assert len(lines)==count and all(x.endswith(': OK') for x in lines),(name,len(lines))
    native=Counter()
    for p in basic+errors+preserve:
        native.update(read(p)['audit']['native_bridge_counts'])
    assert set(native)=={'0x2005f228','0x201dc180','0x201d73e0','0x201fd360'}
    fixtures={p.name:read(p)['audit'].get('review_settings_diff') for p in basic if 'raw_half' in p.name}
    records=[
        '# Top-level commands; replay subprocesses and compiler commands follow.',
        'pwd -P',
        'diskutil info /Volumes/Workspace',
        'git status --short --untracked-files=normal',
        'shasum -a 256 -c research/diag_dat_v1/SHA256SUMS',
        'shasum -a 256 -c firmware/package_v36_diag1/CARD_SHA256SUMS',
        '/usr/bin/python3 -I -B research/review_diag/matrix.py',
        '/usr/bin/python3 -I -B research/review_diag/rebuild.py',
        '/usr/bin/python3 -I -B research/review_diag/static_audit.py',
        '/usr/bin/python3 -I -B research/review_diag/summarize.py',
        '/usr/bin/python3 -I -B research/review_diag/seal.py',
        'shasum -a 256 -c research/review_diag/SHA256SUMS',
        '# Invoked replays, including repeated attempts.',
    ]
    for line in (OUT/'local/commands.jsonl').read_text().splitlines():
        d=json.loads(line)
        records.append('/usr/bin/python3 -I -B '+shlex.join(d['argv']))
    rebuild_commands=OUT/'local/rebuild/candidate/local/commands.jsonl'
    for line in rebuild_commands.read_text().splitlines():
        d=json.loads(line)
        records.append(shlex.join(d['argv'])+'  # exit '+str(d['returncode']))
    (OUT/'COMMANDS.txt').write_text('\n'.join(records)+'\n')
    result=dict(verdict='不可以上测试卡',dat_sha256=first['audit']['dat_sha256'],
        elf_sha256=first['audit']['elf_sha256'],body_sha256=first['audit']['body_sha256'],
        original_behavior_cases=len(basic),error_cases=len(errors),
        prepublication_and_reopen_cases=96,withdrawal_cases=72,lens_preservation_cases=3,
        first_service_failure_demonstrations=1,unique_case_records=874,
        setter_counterexample_cases=len(counterexamples),
        settings_value_change_cases=44,same_value_setter_cases=12,
        counterexample_setter_hits=sum(x['setter_hits'] for x in counterexamples),
        counterexamples=counterexamples,
        positive_case_native_bridge_counts=dict(native),
        positive_case_DAT_rpc8=0,positive_case_DAT_file_calls=0,positive_case_DAT_queue2=0,
        positive_case_unapproved_DAT_stores=0,
        known_raw_input_fixture_settings_differences=fixtures,
        source_of_row_state='Pinned body image and executed original constructors; critical list values are not hand-preset. Font refs, settings, RTOS/device boundaries remain models.',
        original_delivery_hashes_verified=14022,card_hashes_verified=30,
        rebuild_equal=True,body_card_camera_network_access=False,
        limitation='IRQ-enabled nested native-handler models follow the requested review contract. This does not establish actual RTOS scheduling reachability or physical power-cycle behavior.')
    (OUT/'evidence/summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS evidence aggregation:',len(basic),'existing cases;',len(errors),'error paths;',
          len(counterexamples),'setter counterexamples;',result['settings_value_change_cases'],'S changes')


if __name__=='__main__':
    main()
