"""Retain source and compiled evidence for each changed runtime function."""
from pathlib import Path
import difflib
import json
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, TREE, DAT, save, file_sha, sha

def functions(text):
    found = {}
    for match in re.finditer(r'^(?:static )?(?:int32_t|uint32_t|unsigned|int|void|EngStatus)\s+(\w+)\([^;{}]*\)\s*\{', text, re.M):
        start = text.index('{', match.start())
        level, end = 1, start + 1
        while level:
            level += (text[end] == '{') - (text[end] == '}')
            end += 1
        found[match.group(1)] = text[match.start():end]
    return found

def main():
    old = ROOT / 'firmware/engine_v43_fix/candidate/containers/product'
    new = TREE / 'candidate/containers/product'
    names = ('adapter.c', 'src/firmware/engine/core/eng_core.c', 'src/firmware/engine/panel/panel_ui.c')
    changed = []
    folder = OUT / 'compiled'
    folder.mkdir(exist_ok=True)
    elf = TREE / 'candidate/local/full-r13/engine.elf'
    reader = __import__('common').load(ROOT / 'tools/native_harness/image_loader.py', 'audit_elf')
    symbols = reader.Elf(elf).symbols
    tool = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    for name in names:
        before, after = functions((old / name).read_text()), functions((new / name).read_text())
        for function, body in after.items():
            if before.get(function) == body and function != 'pn_ui_render':
                continue
            symbol = next((s for s in (function, function + '.constprop.0', function + '.lto_priv.0') if s in symbols), None)
            row = dict(file=name, function=function, source_sha256=sha(body.encode()), symbol=symbol,
                       source_line=(new / name).read_text().index(body))
            row['source_line'] = (new / name).read_text()[:row['source_line']].count('\n') + 1
            if symbol:
                result = subprocess.run([str(tool), '-d', '--disassemble=' + symbol, str(elf)],
                                        capture_output=True, text=True, check=True)
                (folder / (function + '.txt')).write_text(result.stdout)
                row['address'] = hex(symbols[symbol])
            else:
                row['compiled_scope'] = 'Inlined into the retained entry disassembly.'
            changed.append(row)
    adapter = (new / 'adapter.c').read_text()
    core = (new / 'src/firmware/engine/core/eng_core.c').read_text()
    assert 'if(!n.watch_view||n.ui_failed||n.view_lost||!view_owned())return 0;' in adapter
    assert 'for(i=0;i<4;i++)if(n.port.epochs[i]!=root->epoch[i])return 0;' in adapter
    assert 'n.port.epochs[4]=root->epoch[RV_VIEW_E];n.port.epochs[5]=root->epoch[RV_S_E];' in adapter
    assert 'if(g.uncertain&&g.write_started)return ENG_UNCERTAIN;' in core
    assert 'if(offset+2>bytes||!expect(4,page,page)||!rpc(2,at&65535,&value))' in core
    assert 'status=read_live(1,&mismatch);if(status!=ENG_OK)return status;' in core
    assert adapter.count('while(++round<16)') == 2
    assert 'for(attempt=0;attempt<4;' in core and 'for(attempt=0;attempt<2;' in core
    for name in ('compute', 'deep', 'rpc', 't_read', 't_store', 'write_word', 'apply_impl', 'recover_confirmed', 'settings_match'):
        assert functions((old / names[1]).read_text())[name] == functions(core)[name], name
    assert functions((old / names[0]).read_text())['cursor_cache'] == functions(adapter)['cursor_cache']
    old_service=ROOT/'firmware/engine_v43_fix/candidate/engine_services/services.c'
    new_service=TREE/'candidate/engine_services/services.c'
    service_text=new_service.read_text();ui=functions(service_text)['ui_list']
    expected='if(RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56){rv_irq_restore(irq);return RV_STALE;}'
    assert expected in ui
    assert ui.index('irq=rv_irq_save();')<ui.index(expected)<ui.index('if(!rv_ui_capture(r))')
    assert functions(old_service.read_text())['storage']==functions(service_text)['storage']
    for symbol in ('ui_list','rv_call'):
        actual=next((s for s in (symbol,symbol+'.constprop.0',symbol+'.lto_priv.0') if s in symbols),None)
        if actual:
            result=subprocess.run([str(tool),'-d','--disassemble='+actual,str(elf)],capture_output=True,text=True,check=True)
            (folder/(symbol+'.txt')).write_text(result.stdout)
    changed.append(dict(file='candidate/engine_services/services.c',function='ui_list',
        source_sha256=sha(ui.encode()),guard='Native activity 8 and state 56 are required under the IRQ lock before publication.'))
    save('source-safety.json', dict(status='PASS', dat_sha256=file_sha(DAT), elf_sha256=file_sha(elf),
        changed_functions=changed,
        communication_paths=[
            dict(path='complete_read', functions=['validate_live', 'read_live'],
                 address_source='Nine validated map rows and the mapped T page/index.',
                 length='Loop compares exactly the mapped byte count. Odd row edges use aligned protocol halfwords; bytes outside the row are ignored.'),
            dict(path='sentinel', functions=['sentinel_offset', 'read_live'],
                 address_source='Mapped row base plus an aligned internal offset.',
                 length='Exactly two bytes, with offset + 2 <= mapped size checked before X/V.'),
            dict(path='reapply', functions=['eng_retry_live', 'validate_live', 'recover_confirmed', 'apply_impl', 'deep'],
                 address_source='The unchanged validated map, mapped T and explicit B5 neighbor address.',
                 length='Each mapped logical row is restored in full. Leading and trailing protocol neighbor bytes retain their current values, checked by the runtime range guard.')],
        limits=dict(rows=9, max_row_bytes=96, sentinel_halfwords_per_row=1,
                    sentinel_scan_halfwords=48, merge_rounds=16, confirmed_attempts=4, stock_attempts=2),
        native_ui='List publication checks native activity 8 and state 56 under the IRQ lock before native fields are written. cursor_cache retains ownership and state-address checks. H01 view-change records count only DAT-code writes; fixed-body continuation remains outside this change.',
        file_io='No new storage calls. Both initialization capability masks and the storage guard retain the read-only policy.'))
    print('PASS source and compiled safety evidence', len(changed), 'reviewed functions', flush=True)

if __name__ == '__main__':
    main()
