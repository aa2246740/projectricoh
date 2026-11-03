"""Close four compiled-code categories for each changed C function."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols

CARRIERS={
    'list_bind_impl':['list_bind'], 'ig_event':['ig_event'],
    'eng_check_settings':['eng_check_settings'], 'validate_live':['validate_live'],
    'uv_validate':['ig_init'], 'eng_data_accept':['ig_init'],
    'gxr2_tweak_layout':['ig_init'],
}

def main():
    audit=json.loads((OUT/'evidence/static-audit.json').read_text())
    tables=json.loads((OUT/'evidence/compiled-tables.json').read_text())
    binary=json.loads((OUT/'evidence/binary-inventory.json').read_text())
    layout=json.loads((TREE/'candidate/local/full-r13/layout.json').read_text())
    assert audit['dat_sha256']==tables['dat_sha256']==binary['dat_sha256']==PIN==file_sha(DAT)
    assert tables['unclassified_executable_anomalies']==0 and layout['pic_translation_verified']
    prior=json.loads((ROOT/'firmware/engine_v46_ui/candidate/local/full-r13/layout.json').read_text())
    growth=layout['engine_bytes']-prior['engine_bytes']
    normalized=(OUT/'local/normalized-vs-124.patch').read_text()
    moved_tables=[]
    for name in ('ig_panel_open','rv_call'):
        start=normalized.index('--- 124/'+name+'\n')
        end=normalized.find('\n--- ',start+4)
        block=normalized[start:end if end>=0 else None]
        old=re.findall(r'^-(add3 \w+,\w+,#)(-?\d+)$',block,re.M)
        new=re.findall(r'^\+(add3 \w+,\w+,#)(-?\d+)$',block,re.M)
        other=[line for line in block.splitlines() if line.startswith(('+','-')) and not line.startswith(('+++','---','+add3 ','-add3 '))]
        assert old and len(old)==len(new) and not other,(name,block)
        for a,b in zip(old,new):
            assert a[0]==b[0] and int(b[1])-int(a[1])==growth,(name,a,b,growth)
        moved_tables.append(dict(function=name,table_base_changes=len(old),offset_delta=growth,other_instruction_changes=0))
    available=symbols(ELF)
    rows=[]
    for item in audit['changed_functions']:
        name=item['function']
        carriers=CARRIERS[name]
        compiled=[dict(symbol=symbol,**info) for symbol,info in available.items()
                  if re.sub(r'\.(?:constprop|isra|lto_priv)\.\d+','',symbol) in carriers]
        assert compiled,(name,carriers)
        generation_only=name in ('uv_validate','eng_data_accept','gxr2_tweak_layout')
        rows.append(dict(**item,compiled=compiled,
            address_length=('Only generation 124 -> 126 changes; existing section, CRC and range checks are byte-for-byte preserved.' if generation_only else
                'The existing settings_match builds make_plan and compares every plan byte using a leased settings view. '
                'Unchanged make_plan emits at most 16 writes, with Image mode last, WB at 0x6dd/0x6de, '
                'and the existing mode-specific offsets. No new S address or RPC operation.'),
            file_operations='No storage call added. The linked loader retains read-only capabilities; packaging is a separate host operation.',
            native_UI=('Only the generation comparison changes in this compiled carrier.' if generation_only else
                'Publication checks run after RV_UI_LIST returns; H07 checks run after start_view/retry_view and before confirmation. '
                'The permanent error latch still skips settings repair. Native redraw still has the inherited final scheduling window '
                'and can write 0x205d4f64. No atomic-publication or physical-display claim.'),
            loops_memory=('Generation literal replacement adds no loop or storage.' if generation_only else
                'The new helper has no loop. settings_match iterates the existing plan count <=16. '
                'Restoration reuses apply_impl; confirmed recovery remains at most four attempts plus two stock attempts. '
                'The inherited nine rows, bounded row lengths and 16 navigation rounds are unchanged. No allocation or variable-length array.')))
    stack={}
    for path in (TREE/'candidate/local/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        for line in path.read_text().splitlines():
            fields=line.split('\t')
            if len(fields)==3:
                stack[fields[0].rsplit(':',1)[-1]]=dict(bytes=int(fields[1]),kind=fields[2])
    assert stack and all(row['kind']=='static' for row in stack.values())
    assert layout['engine_bytes']<=65536 and layout['file_bytes']<=65536
    assert layout['file_bytes']+layout['bss_bytes']<=114688
    result=dict(status='PASS_FOUR_CATEGORIES',dat_sha256=PIN,elf_sha256=file_sha(ELF),
                categories=['地址与长度','文件操作','原生界面写入','循环与内存'],
                changed_C_functions=rows,stack=stack,maximum_static_frame=max(row['bytes'] for row in stack.values()),
                engine_bytes=layout['engine_bytes'],file_bytes=layout['file_bytes'],bss_bytes=layout['bss_bytes'],
                PIC_translation_verified=True,switch_words=tables['switch_words'],
                unclassified_executable_anomalies=0,binary_comparison=binary['comparisons'][0],
                additional_compiled_carriers=moved_tables,
                scope='Final source, linked ELF/DAT, retained assembly, static frames and inherited bounded loops. '
                      'Runtime results are separately required by acceptance.json. No RTOS stack or camera acceptance.')
    save('evidence/codegen-safety.json',result)
    print(result['status'],len(rows),'changed C functions; maximum static frame',result['maximum_static_frame'])

if __name__=='__main__':
    main()
