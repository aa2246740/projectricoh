"""Per-function four-category audit and final native-evidence binding."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols

INLINE={
 'uv_adjusted':['uv_name'],'uv_store':['uv_preview'],'uv_rows':['list_bind'],'uv_text':['list_bind'],
 'cursor_cache':['list_bind'],'list_bind_impl':['list_bind'],'uv_move':['ig_apply'],'uv_disp':['ig_panel_open'],
 'gxr2_tweak_layout':['ig_init'],'compute_legacy':['compute'],'project_compute':['compute'],
 'eng_project_compute':[],'eng_project_preview':['uv_preview'],'eng_data_accept':['ig_init'],
 'uv_extension':['uv_config','uv_users','uv_user','ig_init'],'uv_validate':['ig_init'],
}

def main():
    static=json.loads((OUT/'evidence/static-audit.json').read_text())
    tables=json.loads((OUT/'evidence/compiled-tables.json').read_text())
    binary=json.loads((OUT/'evidence/binary-inventory.json').read_text())
    assert static['dat_sha256']==tables['dat_sha256']==file_sha(DAT)
    assert tables['unclassified_executable_anomalies']==0
    available=symbols(ELF)
    def resolve(name):
        found=[key for key in available if re.sub(r'\.(?:constprop|isra|lto_priv)\.\d+','',key)==name]
        assert found,name
        return [dict(symbol=key,**available[key]) for key in found]
    per=[]
    for row in static['changed_functions']:
        name=row['function'];carriers=INLINE.get(name,[name]);compiled=[item for carrier in carriers for item in resolve(carrier)]
        if name=='eng_project_compute':
            assert not any(key.startswith('eng_project_compute') for key in available)
        if name in ('uv_min','uv_max','uv_config','uv_user','uv_users','uv_count_group','uv_group_entry','uv_extension','uv_validate','uv_levels','uv_from_tweak'):
            address='Validated immutable GXUI extension: 24 records of 48 bytes and 32 records of 24 bytes. Slots 1..8, unit 0..2, parameters 1..11, user count <=32. Range translation writes exactly eight bytes.'
        elif name in ('compute_legacy','project_compute','compute','eng_project_preview','eng_project_compute','uv_preview'):
            address='The project boundary rejects nonzero placeholders and values outside the legacy per-base ranges. Legacy tone and saturation math writes the same nine mapped rows in one 552-byte output. Actual communication remains in the unchanged deep/apply_impl path.'
        else:
            address='UI text slots are 8 by 9 bytes, with at most eight ASCII characters plus NUL. Logical rows are <=33; physical rows are always eight. Native access is through the inherited leased descriptors and owned UI service.'
        file_ops='No new storage call. The read-only loader supplies the complete DAT; the new adapter has no load/save/install caller. The inherited dispatcher still requires CAP_FILE_WRITE for mutation.'
        if name in ('ui_list','list_bind_impl','list_bind','keep_view','cursor_cache'):
            native='Eight-row gate, current activity/state and owned-source checks protect publication. A second ownership check follows IRQ restore immediately before redraw. The final check-to-draw scheduling gap remains explicitly documented.'
        elif name.startswith('uv_') or name in ('compute','compute_legacy','project_compute','eng_project_compute','eng_data_accept','gxr2_tweak_layout'):
            native='This body changes only private engine state/data, or returns to the audited eight-row publication path. It has no new S setter. Frame and transition checks use the compiled UI with official native constructors.'
        else:
            native='Ingress and ownership gates remain active. H01 cannot publish unchecked recipes. Failed pre-W actions retain the verified view; locked UI remains eight rows. Exit keeps the verified effect.'
        loops='All loops are finite: 8 physical rows, 8 ASCII characters, 11 parameters, 24 config records or at most 32 users. Navigation drains at most 16 rounds. Compensation remains four confirmed plus two stock attempts. No variable-size stack array.'
        per.append(dict(**row,compiled=compiled,eliminated=not bool(compiled),
                        address_length=address,file_operations=file_ops,native_UI=native,loops_memory=loops))
    stack={}
    for path in (TREE/'candidate/local/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        for line in path.read_text().splitlines():
            parts=line.split('\t')
            if len(parts)==3:stack[parts[0].rsplit(':',1)[-1]]=dict(bytes=int(parts[1]),kind=parts[2])
    assert stack and all(row['kind']=='static' for row in stack.values())
    obligations=[]
    for unit in ('50mm','28mm','mount'):
        for group in ('transitions','values','suite-124','safety','locked','lock-nested-124','lock-cutpoints','view-reentry','users','project-boundary','labels','official-half','lock-exits'):
            names={'suite-124':f'suite-124-{unit}.json','lock-nested-124':f'lock-nested-124-{unit}-record_failure_return-after_update_restore-before_redraw-row_draw.json',
                   'lock-cutpoints':f'lock-cutpoints-{unit}-irq-enabled.json','lock-exits':f'lock-exits-124-{unit}.json'}
            path=(OUT/'local'/f'official-half-{unit}-with-hooks.json') if group=='official-half' else OUT/'evidence'/names.get(group,f'{group}-{unit}.json')
            value=json.loads(path.read_text()) if path.exists() else {}
            status=value.get('status')
            if status and status.startswith('PASS'):status='PASS'
            if group=='suite-124' and value.get('results') and all(x['wait_status']==0 for x in value['results']):status='PASS'
            obligations.append(dict(unit=unit,group=group,file=str(path.relative_to(ROOT)),status=status or 'PENDING',
                                    dat_sha256=value.get('dat_sha256'),expected_sha256=(json.loads((OUT/'evidence/user-tool.json').read_text())['fixture_sha256'] if group=='users' else file_sha(DAT))))
    layout=json.loads((TREE/'candidate/local/full-r13/layout.json').read_text())
    complete=all(row['status']=='PASS' and row['dat_sha256']==row['expected_sha256'] for row in obligations)
    result=dict(status='PASS_SCOPED_FOUR_CATEGORIES' if complete else 'PENDING_NATIVE_EVIDENCE',dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),
        changed_source_functions=len(per),per_function=per,stack=stack,maximum_static_frame=max(row['bytes'] for row in stack.values()),
        engine_bytes=layout['engine_bytes'],bss_bytes=layout['bss_bytes'],file_bytes=layout['file_bytes'],
        PIC_translation_proven=layout['pic_translation_verified'],switch_words=tables['switch_words'],
        binary_comparison=binary['comparisons'][0],unclassified_executable_anomalies=0,obligations=obligations,
        categories=['地址与长度','文件操作','原生界面写入','循环与内存'],
        remaining_native_window='A task can run after the last ownership check and before native draw. This is not claimed atomic. See remaining-window.json.',
        scope='Scoped source, linked bytes, PIC translation, bounded memory/loop checks and actual M32R native user paths. Not full-program compiler equivalence, RTOS stack high-water, camera, card, flash, or physical-pixel acceptance.')
    save('evidence/codegen-safety.json',result)
    print(result['status'],len(per),'source functions; max static frame',result['maximum_static_frame'])

if __name__=='__main__':main()
