"""Verify the exact final package, code, input identities and complete replay matrix."""
from pathlib import Path
from collections import Counter
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope import *


def verify():
    protected=freeze_check()
    tracer=json.loads((OUT/'tracer-inputs.json').read_text())
    assert len(tracer['files'])==79
    assert all(sha(ROOT/p)==h for p,h in tracer['files'].items())
    dat=PACKAGE/'local/SD_ROOT/GXRCE.DAT'
    compiled=ENGINE/'candidate/local/full-r13'
    elf=compiled/'engine.elf'
    digest=sha(dat);elf_digest=sha(elf)
    raw=dat.read_bytes()
    assert raw==(compiled/'GXRCE.DAT').read_bytes()
    assert int.from_bytes(raw[28:32],'big')==125
    base=ROOT/'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT'
    assert sha(base)=='3b9342ee28c523d7737e320abac1cc37ee3e6c6d122a72d5fe90cd2a3f2ee131'
    assert raw[48:112]==base.read_bytes()[48:112]
    assert raw[212:228]==base.read_bytes()[212:228]
    manifest=json.loads((compiled/'manifest.json').read_text())
    size=json.loads((compiled/'layout.json').read_text())
    assert manifest['sha256']==digest and size['pic_translation_verified']
    assert len(raw)==size['file_bytes']<=65536 and len(raw)+size['bss_bytes']<=114688
    assert all(sha(ROOT/p)==h for p,h in size['sources'].items())
    assert all(sha(ROOT/p)==h for p,h in size['tools'].items())
    sys.path.insert(0,str(ROOT/'tools/native_harness'))
    from image_loader import Elf,Image
    parsed=Elf(elf)
    code=next(s for s in parsed.sections if s['name']=='.engine')
    assert code['data']==raw[code['base']:code['base']+code['size']]
    assert not any(name in parsed.symbols for name in ('eng_menu_open','eng_preview_saved','pn_panel_open','g','ig_bx_init'))
    layout=json.loads((OUT/'layout.json').read_text())
    assert len(layout['fields'])==len(layout['field_order'])==50
    assert len(set(layout['field_order']))==50
    spec=json.loads((ROOT/'research/body_v4_storage/validation/diagnostic_spec.json').read_text())
    assert all(layout['fields'][name]==value for name,value in spec['fields'].items())
    fields=[f for rows in layout['pages'].values() for row in rows for f in row if f!='open_high']
    assert Counter(fields)==Counter(layout['fields'].keys())
    for rows in layout['pages'].values():
        assert len(rows)==7
        for row in rows:
            assert sum(4 if f=='open_high' else layout['fields'][f][1]*2 for f in row)<=8
    body=ROOT/'firmware/package_v36_g120b/SD_ROOT/ilaunch3'
    image=Image(body,'50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008')
    for address,width in layout['fields'].values():
        at=int(address,16)
        assert any(base<=at and at+width<=base+length for section in image.sections
                   for base,length in ((section.base,section.size),(section.bss,section.bss_size)))
    package=json.loads((PACKAGE/'manifest.json').read_text())
    assert len(package['files'])==len(list((PACKAGE/'local/SD_ROOT').iterdir()))==30
    for f in package['files']:
        assert sha(PACKAGE/'local/SD_ROOT'/f['name'])==f['sha256']
        if f['name']!='GXRCE.DAT':
            assert f['sha256']==sha(ROOT/'firmware/package_v36_g120b/SD_ROOT'/f['name'])
    assert [f['name'] for f in package['files'] if f['changed']]==['GXRCE.DAT']
    records=[];summaries=[]
    for unit in ('50mm','28mm','mount'):
        for kind,count in (('nested',36),('loss',8)):
            for error in (False,True):
                summary=OUT/'evidence'/f'{kind}-{unit}{"-error" if error else ""}.json'
                obj=json.loads(summary.read_text());summaries.append(str(summary.relative_to(ROOT)))
                assert obj['status']=='PASS' and obj['dat_sha256']==digest and len(obj['cases'])==count
                for case in obj['cases']:
                    assert case['wait_status']==0
                    records.append(OUT/'local/cutpoints'/(case['case']+'.json'))
        summary=OUT/'evidence'/f'h01-{unit}.json'
        obj=json.loads(summary.read_text());summaries.append(str(summary.relative_to(ROOT)))
        assert obj['status']=='PASS' and obj['dat_sha256']==digest and len(obj['cases'])==40
        for case in obj['cases']:
            assert case['wait_status']==0
            records.append(OUT/'local/h01'/(case['case']+'.json'))
        summary=OUT/'evidence'/f'variants-{unit}.json'
        obj=json.loads(summary.read_text());summaries.append(str(summary.relative_to(ROOT)))
        assert obj['status']=='PASS' and obj['dat_sha256']==digest and len(obj['results'])==8
        for case in obj['results']:
            assert case['status']=='PASS'
            records.append(OUT/'local/variants'/f'{unit}-{case["kind"]}.json')
        records.append(OUT/'local/functional'/f'{unit}.json')
    assert len(records)==411 and len(set(records))==411
    categories=Counter();native=Counter();entry_names=set();captures=0;draws=0
    for path in records:
        result=json.loads(path.read_text());audit=result['audit']
        assert result['status']==audit['status']=='PASS',path
        assert audit['dat_sha256']==digest,path
        assert audit['elf_sha256']==elf_digest,path
        assert not audit['unapproved_writes'] and not audit['prohibited_calls'],path
        assert not audit['native_setters'] and not audit['host_ui_writes'],path
        assert audit['rpc8_calls']==audit['file_api_calls']==audit['queue2_sends']==0,path
        assert set(audit['native_bridge_counts'])<=set(('0x2005f228','0x201dc180','0x201d73e0','0x201fd360')),path
        assert all(e['rows']==8 for e in audit['ui_entries']),path
        assert all(k.split(':')[0] in ('10','11') for k in audit['service_counts']),path
        assert not result.get('late_DAT_UI') and not result.get('late_draws'),path
        categories.update(audit['write_counts']);native.update(audit['native_bridge_counts'])
        entry_names.update(n for e in audit['entries'] for n in e['names'])
        captures+=len(audit['captures']);draws+=len(audit['draws'])
    assert {'ig_bootstrap','ig_init','ig_menu','ig_apply','ig_panel_open','ig_event','ig_panel_event','ig_panel_abort','ig_stop'}<=entry_names
    assert set(native)==set(('0x2005f228','0x201dc180','0x201d73e0','0x201fd360'))
    reproduction=json.loads((OUT/'evidence/reproduction.json').read_text())
    assert reproduction['status']=='PASS' and reproduction['dat_sha256']==digest
    matrix=json.loads((OUT/'evidence/matrix-run.json').read_text())
    assert matrix['status']=='PASS' and len(matrix['jobs'])==21
    result=dict(status='PASS_HOST_V1',generation=125,dat_sha256=digest,elf_sha256=elf_digest,
        baseline_sha256=sha(base),body_sha256=sha(body),protected_inputs=protected,
        v10_spec_hashes=189,tracer_design_hashes=79,profile_H='NOT_IMPLEMENTED',
        package_files=30,fixed_files_identical=29,replay_cases=411,
        nested_keys=216,ownership_loss=48,h01_cutpoints=120,variants=24,functional_units=3,
        units=['50mm','28mm','MOUNT'],rpc8_calls=0,file_api_calls=0,queue2_sends=0,
        original_non_UI_stores=0,native_Image_setters=0,host_UI_preset_stores=0,
        write_counts=dict(categories),native_bridge_counts=dict(native),entry_names=sorted(entry_names),
        captures=captures,draw_calls=draws,code_bytes=size['engine_bytes'],file_bytes=len(raw),
        bss_bytes=size['bss_bytes'],main_block_bytes=7504+((len(raw)+size['bss_bytes']+3)&~3),
        pic_translation_verified=True,body_card_camera_acceptance='NOT_RUN',summaries=summaries)
    save(OUT/'evidence/final-verification.json',result)
    return result


if __name__=='__main__':
    result=verify()
    print(result['status'],result['replay_cases'],'cases;',result['dat_sha256'])
