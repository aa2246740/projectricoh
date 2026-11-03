#!/usr/bin/python3
"""核对 thin 源码边界、实际链接、主机结果和冻结输入。"""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_resident'
E=HERE/'evidence_r2'
VARIANTS=('neutral','one_irom_tune_00','card_combined')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    frozen={}
    for name in ('input_receipt.json','input_receipt_r2.json'):
        for path,item in json.loads((HERE/name).read_text()).items():
            assert sha(ROOT/path)==item['sha256'],path
            frozen[path]=item['sha256']
    proto=ROOT/'firmware/resident_v310_proto/resident'
    thin=ROOT/'firmware/resident_v310_thin/resident'
    unchanged=[]
    for name in ('resident.c','shared.c','loader.c','runtime.c','validate_envelope.inc.c',
                 'resident.ld','bridges.S','abi.h','gxrce.h','v3_checks.c'):
        assert sha(proto/name)==sha(thin/name),name
        unchanged.append(name)
    hooks=(thin/'hooks.c').read_text()
    begin=hooks.index('    if(hook==52){')
    end=hooks.index('    if(hook>=40){',begin)
    restored=hooks[:begin]+hooks[end:]
    restored=restored.replace('rv_close_07[],rv_skip_52[];','rv_close_07[];')
    restored=restored.replace('(hook!=1&&hook!=50)||','hook!=1||')
    restored=restored.replace('    if(hook==50){if(!r->reserved_lane)r->reserved_lane=BO_PENDING;return;}\n','')
    assert restored==(proto/'hooks.c').read_text()
    rows=[]
    for name in VARIANTS:
        out=E/name;m=json.loads((out/'measurement.json').read_text())
        assert m['link_ok'] and m['code_bytes']<=8060 and m['free_above_margin']>=0
        assert m['forbidden_bytes']==0 and m['relocation_bytes']==0
        assert m['layout']['RvRoot']['bytes']==256
        assert m['root']==dict(size=244,vma=0x20054700)
        assert m['root_pins']==dict(size=12,vma=0x200547f4)
        assert sha(out/'resident.bin')==m['resident_sha256']
        assert sha(out/'resident.elf')==m['elf_sha256']
        for filename,value in m['source_sha256'].items():
            p=thin/filename
            if name!='neutral' and filename=='loader.c':
                p=ROOT/'firmware/resident_v310_proto/options'/name/'resident/loader.c'
            assert sha(p)==value,(name,filename)
        for path,value in m['tools_sha256'].items():assert sha(ROOT/path)==value,path
        manifest=json.loads((out/'patch-manifest.json').read_text())
        assert {x['hook'] for x in manifest if x['hook'] in ('H50','H51','H52')}=={'H50','H51','H52'}
        rows.append(dict(variant=name,code_bytes=m['code_bytes'],free_bytes=m['free_above_margin']))
    assert rows[0]['code_bytes']-7428<=600
    compare=[]
    keys=('first_frame','frames','unit_rows_sha256','settings_sha256','record_prefix','native_close_rows')
    for name in VARIANTS:
        for unit in ('50mm','28mm','mount'):
            current=json.loads((E/name/('harness-flow-'+unit+'-c.json')).read_text())
            old=json.loads((ROOT/'research/v310_window/evidence/neutral'/('harness-flow-'+unit+'-c.json')).read_text())
            assert current['status']=='PASS'
            for key in keys:assert current['detail'][key]==old['detail'][key],(name,unit,key)
            compare.append(dict(variant=name,unit=unit,normalized_h01_equal=True))
    boot=[]
    for name in VARIANTS:
        for case in ('unsupported','success','mid-error','retire','my1','my2','my3','unknown','missing','maintenance'):
            r=json.loads((E/name/('boot-'+case+'-c.json')).read_text());assert r['status']=='PASS'
            boot.append(dict(variant=name,case=case,seconds=r['seconds']))
    for filename in ('harness-dirty-50mm-c.json','harness-root50-dirty-50mm-c.json'):
        r=json.loads((E/'neutral'/filename).read_text())
        assert r['status']=='PASS' and r['detail']['dirty_bit_cases']==1952 and not r['entries']
    for name in VARIANTS:
        r=json.loads((E/name/'recovery.json').read_text())
        assert r['status']=='PASS' and r['new_hook_entries']==0 and r['hook_entries']==0
    for unit in ('50mm','28mm','mount'):
        r=json.loads((E/'neutral'/('g153-boot-'+unit+'-c.json')).read_text())
        assert r['status']=='PASS' and r['boot_calls']==r['pure_init_calls']==1
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    assert (HERE/'ABI.md').read_bytes()==(HERE/'ABI_R2.md').read_bytes()
    result=dict(status='PASS',frozen_inputs=len(frozen),unchanged_resident_files=unchanged,
        old_hook_guards_restored_byte_equal=True,word_offset=236,word_bytes=4,
        resident_off_gate=False,off_switch='DAT unsupported',sizes=rows,h01=compare,boot=boot,
        root_bit_flip_cases_per_entry=1952,root_entries_tested=['H01','H50'],
        recovery_variants=3,new_recovery_entry_count=0,
        limitation='host models and update confirmation only; no production DAT colour transaction or camera acceptance')
    (E/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',frozen_inputs=len(frozen),boot_cases=len(boot),
                         h01_cases=len(compare),sizes=rows),ensure_ascii=False))


if __name__=='__main__':main()
