"""Verify research identities, result boundaries, wording and root-relative sums."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study
from facts import UnitImage

TERMS=['at'+'tack','ex'+'ploit','in'+'ject','by'+'pass','hi'+'jack',
       'pay'+'load','adver'+'sarial','mali'+'cious',
       '攻'+'击','注'+'入','对'+'抗','劫'+'持','接'+'管','绕'+'过','恶'+'意','外'+'来']
START=datetime.datetime(2026,10,30,1,18,57,tzinfo=datetime.timezone.utc)


def read(name):
    return json.loads((study.OUT/name).read_text())


def references():
    files=[
        'artifacts/firmware/gxr-1.51/ilaunch3',
        'artifacts/firmware/gxr-1.51/jlaunch3',
        'artifacts/firmware/gxr-1.51/qlaunch3',
        'artifacts/firmware/gxr-1.51/l08firm3',
        'artifacts/downloads/gxr-151.zip',
        'firmware/package_v37_g135/local/SD_ROOT/ilaunch3',
        'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT',
        'research/persist_recipe/REPORT.md',
        'research/persist_recipe/collect.py',
        'research/persist_recipe/replay.py',
        'research/persist_recipe/local/calls.json',
        'research/persist_recipe/local/body-manual.txt',
        'research/g135_v37/REPORT.md',
        'research/emulator_m2c/REPORT.md',
        'research/emulator_m2d/REPORT.md',
        'research/t_persistence/REPORT.md',
        'research/t_recovery/REPORT.md',
        'research/multi_module/REPORT.md',
        'tools/gxr_emulator/build/libgxr_m32r.dylib',
        'tools/gxr_emulator/backend.py',
        'tools/gxr_emulator/image.py',
        'tools/gxr_emulator/storage_run.py',
        'tools/gxr_emulator/speed_snapshot.py',
        'tools/gxr_emulator/observe.py',
        'tools/gxr_emulator/panel.py',
        'tools/gxr_emulator/README.md',
        'research/tooling_m32r/prefix/bin/m32r-elf-objdump',
        'research/tooling_m32r_asm/prefix/bin/m32r-elf-as',
        'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld',
        'research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy',
        'firmware/engine_v53_g135/candidate/engine_services/services.c',
        'firmware/engine_v53_g135/candidate/engine_services/bridges.S',
        'firmware/engine_v53_g135/candidate/containers/product/adapter.c',
        'firmware/engine_v53_g135/candidate/containers/product/src/firmware/engine/core/eng_core.c',
        'firmware/engine_v53_g135/candidate/containers/product/src/firmware/engine/core/eng_data.c',
        'firmware/engine_v53_g135/candidate/containers/product/src/firmware/card_container_v2/common.c',
        'firmware/resident_v37/resident/hooks.c',
        'firmware/resident_v37/resident/loader.c',
        'firmware/resident_v37/resident/shared.c',
    ]
    checkpoint=read('probe-census.json')['checkpoint']
    files.extend([checkpoint,str(Path(checkpoint).with_suffix('.json'))])
    return {rel:dict(size=(study.ROOT/rel).stat().st_size,sha256=study.sha(study.ROOT/rel))
            for rel in files}


def outputs():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')


def evidence():
    assert read('inputs-before.json')==study.inputs(), 'fixed inputs differ'
    assert read('scope-check.json')['outside_write_denied']
    assert read('inputs-after.json')['equal']
    assert not (study.ROOT/'research/.r2-scope-check').exists()
    facts=read('dat-unit-facts.json')
    assert facts['all_24_plans_standard_neutral'] and len(facts['modules'])==3
    for module in facts['modules']:
        image=UnitImage(module['name']+'3')
        assert study.sha(image.path)==module['firmware_sha256']
        assert len(module['records'])==8 and len(module['rows'])==9
        for row in module['rows']:
            assert row['raw_equals_dat_stock'] and row['section']==3
    units=read('unit-start-replay.json')
    assert units['status']=='PASS_FUNCTION_REPLAY' and len(units['cases'])==9
    for row in units['cases']:
        assert row['actual_control']==(2 if row['damaged_checksum'] else row['stored_control'])
    sources=read('s-source-replay.json')
    assert sources['status']=='PASS_FUNCTION_REPLAY' and len(sources['cases'])==4
    imported=[row for row in sources['cases'] if row['case']=='unit_parameter_source']
    assert [(r['s_source_byte'],r['mode'],r['wb']) for r in imported]==[(0,1,[9,9]),(1,4,[11,10])]
    assert all(row['body_tail_preserved'] for row in imported)
    build=read('record-try-build.json')
    assert build['source_sha256']==study.sha(HERE/'record_try.S')
    assert build['binary_sha256']==study.sha(study.OUT/'record-try.bin') and build['bytes']==84
    assert not build['product_build']
    sync=read('sync-replay.json')
    assert sync['status']=='PASS_REFERENCE_REPLAY' and len(sync['cases'])==7
    assert sync['reference_sha256']==build['binary_sha256']
    assert sync['cases'][-1]['all_saved_sums_valid'] and sync['task6_from_gpio_key']
    for row in sync['cases'][:-1]:
        if not row['committed']:
            assert row['s_bytes_changed']==0
        assert row['call']['before']['task']==6 and row['call']['after']['task']==6
        assert row['call']['before']['psw']==row['call']['after']['psw']
    locks=read('probe-locks-task6.json')['rows'][1:]
    assert len(locks)==4
    assert [row['after']['count'] for row in locks]==[0,0xffffffff,0,1]
    assert locks[-1]['stop']['reason']=='max_steps'
    waits=read('probe-wait-task6.json')['rows'][1:]
    assert len(waits)==2 and all(r['result']==0xffffffce and r['stop']['reason']=='return' for r in waits)
    power=read('probe-power-task6.json')
    entries=[r for r in power['rows'] if r.get('case')=='save_entry']
    assert len(entries)==1 and entries[0]['context']['task']==6
    assert read('probe-census.json')['accepted'] is False
    windows=[]
    for path in sorted(study.OUT.glob('*.meta.json')):
        row=json.loads(path.read_text())
        raw=path.with_name(path.name.removesuffix('.meta.json')+'.bin')
        assert study.sha(raw)==row['sha256']
        if 'current_body_equal' in row:
            assert row['current_body_equal']
            assert study.Image().raw(int(row['start'],16),row['size'])==raw.read_bytes()
        windows.append(path.name)
    report=(HERE/'REPORT.md').read_text()
    assert report.splitlines()[0]=='需要机身支持'
    known={item['sha256'] for item in references().values()}
    for text in re.findall(r'`([0-9a-f]{40,})`',report):
        assert len(text)==64 and text in known, 'report identity differs'
    for path in outputs():
        assert not path.is_symlink()
        for term in TERMS:
            assert term not in path.name.lower(), 'filename vocabulary check failed'
        if path.suffix not in ('.bin','.elf','.o'):
            content=path.read_text().lower()
            assert not any(term in content for term in TERMS), 'text vocabulary check failed: '+str(path.relative_to(HERE))
    local=[str(path.relative_to(study.ROOT)) for path in outputs() if path.is_relative_to(study.OUT)]
    ignored=subprocess.run(['git','check-ignore','--stdin'],cwd=study.ROOT,
               input='\n'.join(local)+'\n',capture_output=True,text=True,check=True)
    assert set(ignored.stdout.splitlines())==set(local)
    return dict(windows=len(windows),unit_cases=9,s_source_cases=4,sync_cases=7,
                static_recipe_records=24,static_unit_rows=27,
                independent_device_acceptance='NOT_STARTED')


def sums():
    seen=set()
    for line in (HERE/'SHA256SUMS').read_text().splitlines():
        digest,rel=line.split('  ',1)
        path=study.ROOT/rel
        assert not rel.startswith('/') and rel not in seen
        path.resolve().relative_to(study.ROOT)
        assert study.sha(path)==digest, rel
        seen.add(rel)
    assert {str(p.relative_to(study.ROOT)) for p in outputs()} <= seen
    return len(seen)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('seal','check'))
    args=parser.parse_args()
    state=evidence()
    if args.action=='seal':
        refs=references()
        study.save('reference-inputs.json',refs)
        now=datetime.datetime.now(datetime.timezone.utc)
        elapsed=(now-START).total_seconds()
        assert 0<=elapsed<=9000
        study.save('validation.json',dict(status='PASS_RESEARCH_ARTIFACT',
                   started=START.isoformat(),finished=now.isoformat(),
                   elapsed_seconds=elapsed,timebox_seconds=9000,
                   protected_trees_and_files=len(read('inputs-before.json')),
                   vocabulary_ok=True,output_scope='research/persist_recipe_r2',
                   verify_source_sha256=study.sha(HERE/'verify.py'),**state))
        files={study.ROOT/rel for rel in refs}
        files.update(outputs())
        (HERE/'SHA256SUMS').write_text(''.join(study.sha(p)+'  '+str(p.relative_to(study.ROOT))+'\n' for p in sorted(files)))
    else:
        validation=read('validation.json')
        assert validation['status']=='PASS_RESEARCH_ARTIFACT'
        assert validation['verify_source_sha256']==study.sha(HERE/'verify.py')
        assert read('reference-inputs.json')==references()
    count=sums()
    print(json.dumps(dict(status='PASS_RESEARCH_ARTIFACT',sums=count,**state)))


if __name__=='__main__':
    main()
