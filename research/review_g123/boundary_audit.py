"""Classify changed compiled carriers, dispatcher tables and review limits."""
from pathlib import Path
import json
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from static_audit import functions, symbols


def main():
    static = json.loads((OUT/'evidence/static-audit.json').read_text())
    inventory = json.loads((OUT/'evidence/binary-inventory.json').read_text())
    syms = symbols(ELF)
    reader = load(ROOT/'tools/native_harness/image_loader.py', 'boundary_elf_reader')
    elf = reader.Elf(ELF)
    engine = next(s for s in elf.sections if s['name']=='.engine')
    raw, base = engine['data'], engine['base']
    listing = (OUT/'local/engine-123.disasm').read_text()
    instructions = {}
    for line in listing.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$',line)
        if m:
            instructions[int(m[1],16)] = (len(bytes.fromhex(m[2])),m[3])
    tables = []
    table_bytes = set()
    # The preceding compiled range checks bound the two switches to 14 and
    # 13 entries. Both load a relative word and add its table base.
    for start, count in ((0x279c,14),(0x2894,13)):
        targets=[]
        for i in range(count):
            target=start+struct.unpack_from('>i',raw,start-base+4*i)[0]
            assert target in instructions,(hex(start),i,hex(target))
            assert not any(lo<=target<lo+4*n for lo,n in ((0x279c,14),(0x2894,13)))
            assert 'unknown' not in instructions[target][1]
            targets.append(hex(target))
            table_bytes.update(range(start+4*i,start+4*i+4))
        tables.append(dict(start=hex(start),entries=count,targets=targets))
    rv=syms['rv_call']
    anomalies=[]
    for pc,(length,asm) in instructions.items():
        if rv['address']<=pc<rv['address']+rv['size'] and any(x in asm for x in ('unknown','.short','.word','(bad)')):
            assert all(x in table_bytes for x in range(pc,pc+length)),(hex(pc),asm)
            anomalies.append(hex(pc))
    changed=next(c for c in inventory['comparisons'] if c['generation']==122)
    expected={'deferred_menu','finish','fresh','ig_init','ig_menu','keep_view',
              'rebind_impl','rv_call','ui_finish','validate_live'}
    assert {x['name'] for x in changed['changed']}==expected
    assert changed['added']==['ui_list']
    final=TREE/'candidate'
    core_path=Path('containers/product/src/firmware/engine/core/eng_core.c')
    service_path=Path('engine_services/services.c')
    current=functions((final/core_path).read_text())
    prior=functions((ROOT/'firmware/engine_v43_fix/candidate'/core_path).read_text())
    assert all(current[n][0]==prior[n][0] for n in ('validate_live','rebind_impl','eng_require_recheck',
        'compute','rpc','deep','t_read','t_store','write_word','apply_impl','recover_confirmed','settings_match'))
    services=functions((final/service_path).read_text())
    old_services=functions((ROOT/'firmware/engine_v44_keep/candidate'/service_path).read_text())
    assert services['storage'][0]==old_services['storage'][0]
    map_rows=static['maps']
    maximum=max(row['entry_offset']+row['bytes'] for unit in map_rows for row in unit['rows'])
    assert maximum==551
    reasons={
        'deferred_menu':'H01 releases an unchecked view, or binds the existing permanent ERR state.',
        'finish':'The inlined eng_require_recheck store loses Engine.full_check.',
        'fresh':'The unchanged six-epoch same_epoch helper is inlined after its other caller is removed.',
        'ig_init':'Engine zero-fill length changes from 2544 to 2540 bytes.',
        'ig_menu':'The unchanged menu_list and accept_menu_preview helpers are now inlined here.',
        'keep_view':'Adds op 2 ERR shape update, disables panel input, then op 3 redraw.',
        'rebind_impl':'Removes the sentinel-only full_check state update.',
        'rv_call':'ui_list is outlined by noinline; the two switch tables still have 27 classified destinations.',
        'ui_finish':'The inlined eng_require_recheck store loses Engine.full_check.',
        'validate_live':'Restores gen 121 full nine-row and T validation; compiled generator ran 889 cases.',
        'ui_list':'Adds old-owner validation for op 2 inside IRQ, with a bounded 40-byte descriptor.'}
    save('evidence/review-boundaries.json',dict(
        status='NATIVE_UI_BOUNDARY_FAIL',dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),
        source_changed_functions=6,source_mapped_compiled_spans=7,
        other_changed_compiled_carriers=['fresh','ig_init','ig_menu','rv_call'],
        normalized_unchanged_bodies=len(changed['normalized_identical']),
        compiled_carrier_classification=reasons,dispatcher_tables=tables,
        dispatcher_decode_anomalies_classified_as_table=anomalies,
        unclassified_changed_executable_bytes=0,
        maximum_entry_end=maximum,entry_bytes=552,
        categories=[
            dict(category='address_and_length',status='PASS_SCOPED',
                 evidence='DAT/ELF/engine binding, exact gen 121 maps/rows, 889 final compiled validator runs, 27 switch destinations and raw-stream address audit.'),
            dict(category='file_operations',status='PASS_SCOPED',
                 evidence='No added storage call; unchanged storage service rejects write operations in the native storage case. Every completed native session has zero file mutation counters.'),
            dict(category='native_UI',status='FAIL',
                 evidence='IRQ-protected op 2 old-owner checks pass. The new one-row inflight window permits busy H08 to reach the native S setter. Post-IRQ op 3 can redraw an old view after ownership loss.'),
            dict(category='loops_and_memory',status='PASS_SCOPED',
                 evidence='Nine rows at most 96 B, entry end 551 <= 552, navigation 16 rounds, recovery 4+2, new descriptor 40 B, static maximum frame 172 B. No RTOS stack-high-water claim.')],
        scope='Incremental review only. No global compiler-equivalence proof, camera run, RTOS scheduling frequency, exposure completion or persistent-S claim.'))
    print('Classified 7 source-mapped spans, 4 additional compiled carriers and 27 switch destinations; native UI FAIL')


if __name__=='__main__':main()
