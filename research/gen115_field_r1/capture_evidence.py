"""Bind source excerpts, symbol offsets and field classifications to frozen files."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import boundary as b
import artifacts as a
import json
import re
import struct

def main():
    raw,modules=a.parse();e=a.ENGINE
    layout=json.loads((e/'local/staged/layout.json').read_text())
    hashes={p:b.sha(b.add(b.ROOT/p)) for p in layout['sources']}
    assert hashes==layout['sources'], 'final layout source identity mismatch'
    elf_path=b.add(e/'candidate/local/full-r13/engine.elf');elf=elf_path.read_bytes()
    assert elf[:6]==b'\x7fELF\x01\x02'
    shoff=struct.unpack_from('>I',elf,32)[0];stride,num,strings=struct.unpack_from('>3H',elf,46)
    sections=[struct.unpack_from('>10I',elf,shoff+i*stride) for i in range(num)]
    string_sec=sections[strings];names=elf[string_sec[4]:string_sec[4]+string_sec[5]]
    engine=next(s for s in sections if names[s[0]:].split(b'\0',1)[0]==b'.engine')
    code=elf[engine[4]:engine[4]+engine[5]]
    assert code==raw[engine[3]:engine[3]+engine[5]], 'ELF machine code differs from DAT'
    native=a.read(b.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3')
    locations=[]
    for name,va in [('H01',0x2028709c),('H06',0x202be24c),('H07',0x202871d8),('H08',0x202bb968),
                    ('H09',0x2017098c),('open',0x200a40b4),('create',0x200a544c),('create_inner',0x200a41ac),
                    ('FAT_create',0x200a554c),('FAT_lookup_mode',0x200b4824),('FAT_find_free',0x200b6d08),
                    ('FAT_free_slot_test',0x200b6f80),('FAT_name_lookup',0x200b62a8),('FAT_write_permission',0x200ab080),
                    ('native_row_to_mode',0x2037f492),('confirm_keep1_call',0x202c2d70),('confirm_keep0_call',0x202c2d80)]:
        data,off,section=a.native_span(native,va,4)
        locations.append(dict(name=name,vma=hex(va),file_offset=hex(off),section=section,bytes=data.hex()))
    (b.LOCAL/'source_excerpt.txt').write_text('')
    product='firmware/engine_v36_r28/candidate/containers/product/'
    root='firmware/resident_v34c/resident/'
    service='firmware/engine_v36_r28/candidate/engine_services/'
    sources={product+'adapter.c':[(58,102),(144,151),(186,242),(292,330),(339,369),(415,518),(545,554)],
        product+'blackbox.c':[(1,137)],
        product+'src/firmware/engine/core/eng_core.c':[(42,97),(110,120),(164,209),(224,272),(294,347),(374,378)],
        product+'src/firmware/engine/core/eng_data.c':[(1,77)],
        service+'api.c':[(11,51)],service+'services.c':[(9,18),(224,255),(257,299),(324,344)],
        service+'bridges.S':[(28,73)],service+'mark.c':[(18,54)],
        root+'hooks.c':[(5,90)],root+'resident.c':[(2,15),(22,71)],root+'loader.c':[(7,58),(62,139)],
        root+'resident.h':[(6,35)],root+'build.py':[(73,104)],
        'research/gr4_lut_ceiling/bridge.py':[(77,126)],
        'research/r28_bank_design/DESIGN.md':[(108,141)]}
    text=[]
    for rel,ranges in sources.items():
        path=b.add(b.ROOT/rel);lines=path.read_text().splitlines()
        text.append(f'FILE {rel} SHA256 {b.sha(path)}')
        for lo,hi in ranges:
            text.extend(f'{i:5d} {lines[i-1]}' for i in range(lo,min(hi,len(lines))+1))
        text.append('')
    (b.LOCAL/'source_excerpt.txt').write_text('\n'.join(text)+'\n')
    out=dict(native=locations,engine=dict(elf_sha256=b.sha(elf_path),code_matches_final_DAT=True,
        code_DAT_offset=hex(engine[3]),code_ELF_file_offset=hex(engine[4]),code_bytes=engine[5],
        address_rule='runtime VMA = relocated image_base + DAT offset; runtime image_base not supplied by retained logs',
        functions={name:hex(value) for name,value in layout['entries'].items()}),source_hashes_match_final_layout=True,
        records=[dict(unit=m['name'],records=[dict(slot=s,mode=m['records'][s][3],
                    file_offset=hex(m['bank_offset']+32+(s-1)*64),wb=list(m['records'][s][49:51]),
                    bytes=m['records'][s].hex()) for s in (1,2,3,4)]) for m in modules])
    b.dump('identity_and_locations.json',out)
    results=json.loads((b.LOCAL/'image_results.json').read_text())['results']
    for r in results:
        assert not any('error' in k for k in r['metadata'])
        assert r['metadata']['selector']==r['jpeg_metadata']['selector']
        assert r['metadata']['raw13']==r['jpeg_metadata']['raw13']
    by_id={r['id']:r for r in results}
    assert by_id['R8051478']['metadata']['raw13']==by_id['R8051476']['metadata']['raw13']
    assert by_id['R8051479']['metadata']['raw13']==by_id['R8051477']['metadata']['raw13']
    assert by_id['R8051478']['metadata']['selector']==9 and by_id['R8051479']['metadata']['selector']==1
    assert by_id['R8051479']['errors']['04']['median']<.75
    assert by_id['R8051479']['errors']['02']['median']>3
    prior=json.loads((b.ROOT/'research/gr4_lut_ceiling/local/bridge/native.json').read_text())
    for old in prior:
        assert abs(old['stock_row5_model_error']['median']-by_id[old['id']]['errors']['04']['median'])<1e-10
    b.dump('acceptance.json',dict(final_source_and_machine_identity=True,old04_controls_reproduced=True,
        JPEG_DNG_image_setting_fields_equal=True,field_native_selector_mapping=[9,1],
        no_firmware_built=True,no_hardware_or_network_used=True,native_harness_execution=False,
        native_harness_reason='available bridge lists generations 113/114, not 115; active worker tree left untouched',
        model_classification='no full 01/02 in captured JPEGs; transient earlier writes unobservable',
        input_changes_checked_by='boundary.py verify'))
    b.dump('development_errors.json',[dict(script='images.py',error='unsupported vividness=130 assertion on native1476 control',
        resolution='retained frozen 100-percent 04 model; added separate deterministic official A7/B7/vivid130 control; no frozen guard relaxed'),
        dict(script='report.py',error='literal NUL in generated text from unit-name escape',
        resolution='changed report template to raw text and added a no-NUL sealing assertion')])
    b.verify()
    print('PASS exact old04 residuals reproduced; JPEG/DNG metadata agree; final sources and ELF match DAT')

if __name__=='__main__':main()
