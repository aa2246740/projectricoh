#!/usr/bin/python3
"""Summarize completed receipts without treating a process exit as acceptance."""
import hashlib
import json
from pathlib import Path
import zlib

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'


def read(name):return json.loads((E/name).read_text())


def colour_count(detail,first):
    return sum(row['step']>=first for row in detail['dirty_settings_writes'])


def initialized_words(detail):
    words=[row['word'] for row in detail['fixed_word_changes']]
    # The native-width observer sees each byte of the initial resident clear.
    return words[words.index(0):]


def main():
    result=dict(image_sha256=read('build.json')['image_sha256'])
    rows=[]
    identity_files=['identity-28mm-c-r2.json','identity-28mm-diag-c-r4.json',
                    'identity-50mm-c-r1.json','identity-mount-c-r1.json']
    for file in identity_files:rows+=read(file)['cases']
    assert len(rows)==21 and len({(r['unit'],r['case']) for r in rows})==21
    assert all(r['status']=='PASS' and not r['resident_ram_replaced'] for r in rows)
    py=read('identity-28mm-python-r1.json')['cases']
    assert len(py)==7 and all(r['status']=='PASS' for r in py)
    result['identity']=dict(cases=21,passed=21,python_cases=7,python_passed=7)
    units=[]
    for unit in ('50mm','28mm','mount'):
        native=read(f'nodat-{unit}-r1.json');nd=read(f'nodat-{unit}-r1-detail.json')
        release=read(f'release-{unit}-r2.json');rd=read(f'release-{unit}-r2-detail.json')
        assert [s['state'] for s in native['state_sequence']]==[0,2,32,5]
        assert nd['counts']['H50']==1 and not any(c['op']==257 for c in nd['calls'])
        assert [x['word'] for x in nd['fixed_word_changes']].count(1)==1
        assert nd['final']['word']==2
        assert initialized_words(nd)==[0,1,2]
        calls=[c for c in rd['calls'] if c['op']==257]
        assert len(calls)==1
        call=calls[0];reply=bytes.fromhex(call['reply'])
        assert call['result']==0 and int.from_bytes(reply[4:8],'big',signed=True)==-4
        assert rd['final']['word']==2 and rd['final']['root_state']==3
        assert initialized_words(rd)==[0,1,2]
        assert nd['final']['s_sha256']==rd['final']['s_sha256']
        assert not rd['final']['rpc_state']
        assert colour_count(rd,release['first_state5']['step'])==0
        units.append(dict(unit=unit,nodat_first5=native['first_state5'],release_first5=release['first_state5'],
            release_boot_start=call['step'],release_boot_return=call['return_step'],
            release_status=-4,release_W=0,release_S=0,release_T=0,
            release_colour_scope='DAT colour writes; native cold initialization is excluded',
            release_root=3,word=2))
    result['cold']=units
    valid=[]
    for name in ('record-mount-builtin-r1','record-mount-look-r1','record-mount-user-r1',
                 'record-28mm-builtin-r1','record-50mm-user-r1'):
        m=read(name+'.json');d=read(name+'-detail.json');r=read(name+'-record.json')
        record=bytes.fromhex(r['record'])
        assert record[:5]==b'GXR2\3' and zlib.crc32(record[:36])==int.from_bytes(record[36:],'big')
        assert r['source_events'] and r['native_state_presets']==[]
        dat=(HERE.parents[1]/'firmware/package_v310_g155_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
        assert record[28:36]==dat[20:28]
        assert r['root_state']==6 and r['word']==2 and not r['target_equal']
        assert r['native_activity']==0 and r['check_failure']==2
        boot=[c for c in d['calls'] if c['op']==257]
        assert len(boot)==1 and boot[0]['result']==3
        assert colour_count(d,m['first_state5']['step'])==0 and not d['final']['rpc_state']
        assert initialized_words(d)==[0,1,2]
        valid.append(dict(name=name,status='FAIL',reason='BOOT activity qualification requires 8; native value is 0',
            source='记录来源为声明放置，非真实手动保存',first5=m['first_state5']['step'],
            boot_entry=boot[0]['step'],boot_return=boot[0]['return_step'],
            steps_first5_to_refusal=boot[0]['return_step']-m['first_state5']['step'],
            W=0,S=0,T=0,DIRTY=0,GUARD=0,target_equal=False))
    result['valid_records']=dict(required_cases=5,passed=0,failed=5,cases=valid)
    shutter=[]
    for unit in ('50mm','28mm','mount'):
        p=E/f'h52-{unit}-r1-source.json'
        if not p.exists():continue
        d=json.loads(p.read_text())
        for phase in ('DIRTY-word-fixture','GUARD-word-fixture'):
            for raw in (13,14):
                hits=[x for x in d['keys'] if x['phase']==phase and x['raw']==raw and x['pressed']==1]
                assert hits and all(x.get('path')=='cancel' and x.get('result')==0 for x in hits)
        assert any(x['phase']=='clear-word' and x['raw']==13 and x['pressed']==1 and x.get('path')=='continue' for x in d['keys'])
        assert d['final_word']==2 and not d['native_state_presets']
        shutter.append(dict(unit=unit,resident_word_contract='PASS',native_gpio=True,
            owned_word_fixture=True,actual_DAT_DIRTY_timing='OPEN'))
    result['H52']=shutter
    negative=[]
    for name in ('record-mount-badcrc-r1','record-50mm-cross-r1'):
        p=E/(name+'-record.json')
        if not p.exists():continue
        d=json.loads(p.read_text());m=read(name+'.json');detail=read(name+'-detail.json')
        assert d['word']==2 and colour_count(detail,m['first_state5']['step'])==0
        assert not detail['final']['rpc_state']
        negative.append(dict(name=name,colour_writes=0,independent_gate='OPEN',
            reason='Earlier activity qualification rejects before record-specific checks'))
    result['negative_records']=negative
    proofs=[]
    for p in sorted(E.glob('proof-*.json')):
        if p.name.endswith('-process.json'):continue
        d=json.loads(p.read_text())
        if 'observed' in d:
            assert d['result']==0 and d['stop']['reason']=='return'
            assert d['observed'][-1]['offset']=='0x5ef4'
            proofs.append(dict(name=p.stem,backend=d['backend'],steps=d['stop']['steps'],result=0))
    result['pure_gate_proofs']=proofs
    declared=read('declared-records.json')
    for row in declared:
        block=(HERE/'local'/f"{row['name']}-settings.bin").read_bytes()
        baseline=(HERE.parents[1]/row['baseline']).read_bytes()
        assert len(block)==len(baseline)==4096
        assert block[:0xfd4]==baseline[:0xfd4]
        assert hashlib.sha256(block).hexdigest()==row['settings_sha256']
        assert hashlib.sha256(baseline).hexdigest()==row['baseline_sha256']
    result['persistent_source']=dict(cases=len(declared),device=0,lba='0x2b690',sectors=8,
        record_range=['0xfd4','0xffc'],derived_container_checksum=['0xffc','0x1000'],
        other_bytes_equal_native_cold_baseline=True,
        origin='记录来源为声明放置，非真实手动保存')
    candidate=read('recovery-candidate-confirm-r1.json')
    control=read('recovery-v39-confirm-r1.json')
    current=read('recovery-v310-confirm-r5.json')
    assert candidate['card']['files']['ilaunch3']==result['image_sha256']
    for row in (candidate,control,current):
        assert row['steps']==65_975_242 and not row['hooks_or_resident_executed']
    assert candidate['milestones']==control['milestones']==current['milestones']
    assert candidate['counts']==control['counts']==current['counts']
    flash=read('recovery-v310-full-r4-flash.json')
    progress=read('recovery-v310-full-r4-progress.json')
    assert flash['steps']==1_859_053_607 and flash['pc']=='0x2005ccf0' and not flash['complete']
    result['recovery']=dict(candidate_header_confirmation='PASS',
        current_v39_control_sha256=control['image_sha256'],
        v310_confirmation_step=current['steps'],confirmation_milestones_equal=True,
        full_restore='INCOMPLETE',final_image_equality='OPEN',
        last_step=flash['steps'],last_pc=flash['pc'],native_result='not captured in r4',
        native_error_basis='Original UI-return observer stops at this address only for a negative r0',
        programmed_pages=flash['programmed_pages'],confirm_phase=progress['phase'])
    result['open']={
        'manual_save_and_first_ADJ':'Existing NAND boundary stops state 56 before H01',
        'later_32_to_5':'Real GPIO transition stops in state 24 at undeclared unit slot 68',
        'non_04_S':'Not produced through a real native path; no original state fields preset',
        'MY1':'Real dial GPIO produces MY=1 but stops before standby at undeclared unit slot 72',
        'independent_record_gates':'Earlier activity qualification rejects first',
        'actual_DIRTY_shutter_timing':'Valid BOOT never reaches a colour transaction',
        'camera':'No physical card, camera, unit program, or power-loss acceptance in this run'}
    result['verdict']='有缺陷'
    (E/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(identity=21,release=3,valid_record_pass=0,valid_record_fail=5,
                         shutter_contracts=len(shutter),negative_records=len(negative),verdict='有缺陷'),ensure_ascii=False))


if __name__=='__main__':main()
