"""Verify completed final-SHA receipts and publish each priority immediately."""
from pathlib import Path
import argparse
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import accept_r2 as A

def run(label,profile,unit,backend):
    row=A.read(C.LOCAL/'runs'/label/'result.json')
    assert row['status']=='OBSERVED' and row['cold_start'] and not row['snapshots']
    assert row['version']==profile and row['unit']==unit and row['actual_backend']==backend
    assert row['dat_sha256']==A.EXPECTED[profile]
    assert row['body_sha256']==A.BODY
    return row
def native(label,profile,unit):
    r=run(label,profile,unit,'native');samples=r['builtin_samples']+r['samples']+r['user_samples']
    assert len(r['builtin_samples'])==8 and len(r['samples'])==18 and len(r['user_samples'])==3
    assert all(s['full_40_equal'] and s['unit_readback']['complete_552_equal'] for s in samples)
    assert r['DISP_card']['screen']==1 and r['DISP_back']['screen']==0
    assert r['after_close']['state']==r['ADJ_closed']['state']==5 and r['close_record_equal']
    return dict(status='PASS',run=label,unit=unit,profile=profile,records=29,full_40=True,full_552=True,DISP_OK_ADJ=True)
def vivid():
    source=A.DIR/'mount-Vivid09-HCBW-plus1-S.bin';block=source.read_bytes();record=block[0xfd4:0xffc]
    expected=list(struct.unpack('>10h',record[8:28]));rows=[]
    for backend in ('native','reference'):
        label='r9-model-test-mount-Vivid09-'+backend;r=run(label,'test','mount',backend)
        assert r['persistent_vivid_BOOT_skip'] and r['persistent_vivid_menu_not_04']
        assert r['BOOT_W']==0 and r['unit_W']==0
        for point in ('after_boot','first_menu','diagnostic_page','list_after_diagnostic'):
            s=r[point];assert s['selector']==9 and s['memory_result']==1
            assert s['saved_levels']==expected and s['saved_reference']==[2,3] and s['saved_user']==0
            assert s['record']==record.hex() and not s['boot_committed'] and not s['baseline']
        diag=r['diagnostic_page'];assert diag['rows']==8 and diag['screen']==5
        assert diag['diagnostic']['reason']==20 and diag['diagnostic']['failed']&128
        assert diag['text'][0]=='G157B20R03' and diag['text'][1].endswith('A--')
        page=r['list_after_diagnostic'];assert page['screen']==0 and page['rows']==8 and page['root_state']==3
        assert page['cursor']==page['cached']==page['physical']+1
        assert not any(t.startswith('>04') for t in page['text'])
        assert (C.LOCAL/'runs'/label/'menu-S.bin').read_bytes()[0xfd4:0xffc]==record
        fixture=A.read(C.LOCAL/'runs'/label/'service-fixture/manifest.json')
        Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','g157_r2_saved_elf').Elf
        symbol=Elf(C.artifact('test','model')['build']/'engine.elf').symbols['n']['value']
        offsets=A.read(C.LOCAL/'layout.json')['offsets']
        address=fixture['image_base']+symbol+offsets['n.values']+2*20
        region=next(v for v in fixture['regions'] if v['address']<=address and address+20<=v['address']+v['bytes'])
        start=address-region['address'];memory=(C.ROOT/region['file']).read_bytes()
        assert C.sha(memory)==region['sha256']
        ui_cached=list(struct.unpack('>10h',memory[start:start+20]));assert ui_cached==expected
        if backend=='reference':assert r['Vivid_unchanged_since_valid_load']
        rows.append(dict(status='PASS',run=label,backend=backend,selector=9,saved_levels=expected,
            ui_cached_levels=ui_cached,record_preserved=True,colour_W=0,first_ADJ_B20=True,list_published=True,
            selector_stores=r.get('Vivid_selector_stores')))
    A.update(2,dict(status='PASS',utc=A.now(),rows=rows,fixture_sha256=C.sha(block),
        scope='Valid persisted Vivid code 09 throughout full new MAIN, BOOT, first diagnostic and list. No late RAM forcing.'))
def text():
    receipts=[A.read(A.DIR/('ui-text-'+name+'.json')) for name in ('normal','Vivid09')]
    assert all(r['status']=='PASS' and r['DAT_sha256']==A.EXPECTED['test'] for r in receipts)
    assert receipts[0]['frames'][0]['screen']==0 and receipts[1]['frames'][0]['screen']==5
    assert all(len(r['frames'][0]['rows'])==8 for r in receipts)
    A.update(3,dict(status='PASS',utc=A.now(),first_ADJ_rows=16,pixel_screenshot=False,
        files=[str(A.DIR/('ui-text-'+name+ext)) for name in ('normal','Vivid09') for ext in ('.json','.md','.tsv')],
        independent_original_converter=True,scope='Actual UI row descriptors, glyph buffers, per-character mapping; not LCD pixels.'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--step',required=True,type=int);a=p.parse_args();C.setup()
    if a.step==2:vivid()
    elif a.step==3:text()
    elif a.step==4:
        rows=[A.reference_receipt('r9-model-test-'+u+'-critical-reference','test',u) for u in ('50mm','28mm')]
        A.update(4,dict(status='PASS',utc=A.now(),rows=rows))
    elif a.step==5:
        rows=[native('r9-model-release-'+u+'-sweep-native','release',u) for u in ('50mm','28mm')]
        refs=[A.reference_receipt('r9-model-release-'+u+'-critical-reference','release',u) for u in ('50mm','28mm')]
        A.update(5,dict(status='PASS',utc=A.now(),native=rows,reference=refs))
    elif a.step==6:A.update(6,A.reference_receipt('r9-model-release-mount-critical-reference','release','mount'))
    elif a.step==7:
        A.freeze('final')
        references=[]
        for profile in ('test','release'):
            for unit in C.UNITS:
                label='r1-model-test-mount-critical-reference-r2' if profile=='test' and unit=='mount' else 'r9-model-'+profile+'-'+unit+'-critical-reference'
                references.append(A.reference_receipt(label,profile,unit))
        C.save(A.DIR/'reference-final-verification.json',dict(status='PASS',rows=references,semantic_cursor=True))
        A.render(A.read(A.DIR/'receipts.json'))
    elif a.step==8:
        rows=[native('r9-model-release-'+u+'-sweep-native','release',u) for u in ('50mm','28mm')]
        A.update('5_native',dict(status='PASS',utc=A.now(),rows=rows))
    else:raise ValueError(a.step)
    print(json.dumps(dict(step=a.step,status='PASS',report=str(C.HERE/'REPORT.md')),ensure_ascii=False))
if __name__=='__main__':main()
