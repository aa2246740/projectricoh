"""Close the four scoped machine-code safety categories for gen 122 to 123."""
from pathlib import Path
import json,re,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import functions,symbols

def main():
    data=json.loads((OUT/'evidence/static-audit.json').read_text())
    assert data['dat_engine_elf_equal'] and all(data['source_hashes'].values()) and all(data['tool_hashes'].values())
    syms=symbols(ELF);old=ROOT/'firmware/engine_v44_keep/candidate';new=TREE/'candidate'
    core=Path('containers/product/src/firmware/engine/core/eng_core.c')
    base=functions((ROOT/'firmware/engine_v43_fix/candidate'/core).read_text())
    current=functions((new/core).read_text())
    assert current['validate_live'][0]==base['validate_live'][0]
    assert current['rebind_impl'][0]==base['rebind_impl'][0]
    assert current['eng_require_recheck'][0]==base['eng_require_recheck'][0]
    assert set(x['function'] for x in data['changed_functions'])=={'deferred_menu','eng_require_recheck','rebind_impl','validate_live','keep_view','ui_list'}
    assert not any(x in current for x in ('sentinel_offset','read_live','eng_menu_deferred'))
    for row in data['compiled_spans'].values():assert not row['embedded_data_or_decode_anomalies'],row
    tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    dependencies={}
    for name in ('ig_apply','a4_move','recover_confirmed','release_view','rv_call','rv_irq_save','rv_irq_restore'):
        actual=next((x for x in (name,name+'.constprop.0',name+'.lto_priv.0') if x in syms),name)
        text=subprocess.run([str(tool),'-d','--disassemble='+actual,str(ELF)],capture_output=True,text=True,check=True).stdout
        (OUT/'local/compiled'/(actual+'.txt')).write_text(text)
        dependencies[name]=dict(symbol=actual,**syms.get(actual,{}),disassembly_sha256=sha(text.encode()))
    apply=(OUT/'local/compiled/ig_apply.txt').read_text();move=(OUT/'local/compiled/a4_move.txt').read_text()
    for token in ('ldi r4,#16 -> st r4,@sp','ld r5,@sp -> addi r5,#-1'):assert token in apply,token
    for token in ('ldi fp,#16','addi fp,#-1','beqz fp,'):assert token in move,token
    deferred=(OUT/'local/compiled/deferred_menu.txt').read_text()
    assert '<release_view>' in deferred and '<list_bind>' in deferred and '<finish>' in deferred
    assert not any(x in deferred for x in ('<rpc','<write_word','<apply_impl','<rv_native_write','<rv_native_create'))
    # Retain gen 122's publication check and all four compensation bounds.
    services=Path('engine_services/services.c')
    assert functions((old/services).read_text())['storage'][0]==functions((new/services).read_text())['storage'][0]
    service=(new/services).read_text()
    assert 'if(RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56){rv_irq_restore(irq);return RV_STALE;}' in service
    core_text=(new/core).read_text()
    assert 'attempt<4' in core_text and 'attempt<2' in core_text
    stack={}
    for path in (new/'local/product-r13/m32r-lto').glob('engine.elf.ltrans*.su'):
        for line in path.read_text().splitlines():
            parts=line.split('\t')
            if len(parts)==3:stack[parts[0].rsplit(':',1)[-1]]=dict(bytes=int(parts[1]),kind=parts[2])
    assert stack and all(x['kind']=='static' for x in stack.values())
    layout=json.loads((OUT/'local/layout/layout.json').read_text())
    assert layout['bytes']==2540 and layout['recheck']==2539
    machine=json.loads((OUT/'evidence/machine-verify.json').read_text())
    assert machine['status']=='PASS'
    phase=MATERIALS/'local/p1-verified'
    assert (new/core).read_bytes()==(phase/'source/candidate'/core).read_bytes()
    old_adapter=functions((phase/'source/candidate/containers/product/adapter.c').read_text())
    new_adapter=functions((new/'containers/product/adapter.c').read_text())
    for fn in ('record_failure','deferred_menu','retry_view','ig_menu','ig_apply','ig_event','ig_panel_open'):
        assert old_adapter[fn][0]==new_adapter[fn][0],fn
    ui_symbol=next(x['compiled'][0]['symbol'] for x in data['changed_functions'] if x['function']=='ui_list')
    bind=(OUT/'local/compiled'/(ui_symbol+'.txt')).read_text()
    assert '<rv_irq_save>' in bind and '<rv_irq_restore>' in bind
    assert 'previous.state_address=s->view_source;previous.rows=s->rows;' in service
    assert '<rv_native_context>' not in bind
    categories=[
      dict(category='地址与长度',status='PASS',evidence='validate_live is byte-for-byte gen 121 source. Frozen P1-phase compiled read-generator evidence covers all three maps and every read failure cut. Its core source is unchanged in the final increment; native restore cases separately exercise W.',
           bound='Nine rows, maximum 96 logical bytes; aligned halfword edges require preserved adjacent bytes.'),
      dict(category='文件操作',status='PASS_STATIC',evidence='No new storage caller. deferred_menu can only release the view or publish the existing latched ERR list. Write capability remains absent; native service rejection and session mutation counters are checked separately.'),
      dict(category='原生界面写入',status='PASS_STATIC',evidence='H01 failure takes the existing release_view. The gen 122 activity/state STALE guard remains literal-identical. New op 2 checks previous ownership inside the existing IRQ boundary before changing list shape; op 3 checks ownership before redraw. Native cases cover owned and lost-owner latch publication.'),
      dict(category='循环与内存',status='PASS',evidence='Removed sentinel scan. Full read is bounded by nine validated descriptors and halfword lengths. The UI update adds one bounded 40-byte stack descriptor and no new loop. Navigation still has sixteen rounds, compensation four plus two.',
           engine_bytes=layout['bytes'],maximum_static_frame=max(x['bytes'] for x in stack.values()))]
    save('evidence/codegen-safety.json',dict(status='PASS_STATIC_BOUNDARIES_AND_TARGETED_M32R',
      dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),changed_functions=6,compiled_spans=len(data['compiled_spans']),
      undecoded_changed_executable_bytes=0,full_validator_equals_gen121=True,rebind_equals_gen121=True,
      H01_publication_guard_equals_gen122=True,publication_services_equals_gen122=False,removed_functions=['sentinel_offset','read_live','eng_menu_deferred'],
      machine_cases=machine['count'],machine_evidence_dat_sha256=machine['dat_sha256'],
      core_source_identical_to_verified_phase=True,lock_rule_and_H01_source_identical_to_verified_phase=True,
      categories=categories,dependencies=dependencies,stack=stack,
      maximum_static_frame=max(x['bytes'] for x in stack.values()),
      scope='Scoped machine-code safety closure, with inherited service paths and separately recorded native cases. New locked-display paths use existing op 2 update and op 3 redraw, with the old-owner check inside the existing UI service IRQ boundary. P1 read-generator evidence is retained from its frozen phase; only related lock tests rerun on the final DAT. No global compiler equivalence, RTOS timing, camera, or stack high-water claim.'))
    output=OUT/'evidence/codegen-safety.json'
    record=json.loads(output.read_text());record['per_function']=[{'function': 'deferred_menu', 'address_length': 'No new RPC. The non-latched branch sets recheck then calls existing release_view.', 'file_operations': 'No storage caller.', 'native_UI': 'Unchecked H01 releases the view. Only the existing latched ERR branch calls list_bind(1).', 'loops_memory': 'No new loop or buffer; two bounded single-byte state stores.'}, {'function': 'eng_require_recheck', 'address_length': 'One byte at Engine+2539 inside sizeof(Engine)=2540.', 'file_operations': 'No call.', 'native_UI': 'No native UI store.', 'loops_memory': 'Single store; mapped to keep_view, deferred_menu, finish and ui_finish.'}, {'function': 'rebind_impl', 'address_length': 'Same as gen 121; snapshot has fixed buffer sizes, epoch copy is 28 bytes at Engine+156.', 'file_operations': 'No storage call.', 'native_UI': 'No native UI store.', 'loops_memory': 'No unbounded loop; fixed epoch copy and three state-byte stores.'}, {'function': 'validate_live', 'address_length': '889 compiled cases cover complete nine-row/T read generation, failure cuts and mismatch detection; W delegates are unchanged and tested natively.', 'file_operations': 'No storage caller.', 'native_UI': 'No list publication. Native settings read/repair paths are unchanged and checked by the native matrix and settings fault case.', 'loops_memory': 'Nine rows, at most 96 B each, settings plan bounded to 16; full validator source equals gen 121.'}]
    record['per_function'].extend([
        dict(function='ui_list',address_length='Existing rows/cursor/range checks precede the new op 2 ownership gate. The previous descriptor is a bounded 40-byte copy. No new RPC.',
             file_operations='No storage caller.',native_UI='Inside the existing UI-service IRQ boundary, op 2 checks the previous live rows/source before updating to the validated new shape. Context query and UI preparation precede IRQ save; redraw remains op 3 after restore.',
             loops_memory='Existing bounded row/text loops and a 40-byte stack descriptor. No native service or draw is called inside the IRQ region. Cached UI is reused for an owned update.'),
        dict(function='keep_view',address_length='No new RPC or buffer.',file_operations='No storage caller.',
             native_UI='A latched owned view uses list_bind(2), clears panel input, then list_bind(3). Lost ownership returns before native UI changes and retains next-H01 ERR.',
             loops_memory='Two finite UI calls; the unlocked retained-view branch is unchanged.')])
    record['irq_bound']='No outer IRQ wrapper. Existing context query and UI preparation run before ui_list saves IRQ; op 2 checks old ownership before writes. Op 3 draws after IRQ restoration.'
    save('evidence/codegen-safety.json',record)
    print('PASS codegen safety: six functions,',len(data['compiled_spans']),'spans, four categories; machine cases',machine['count'])
if __name__=='__main__':main()
