"""Bind source deltas and machine-code spans to the frozen DAT."""
from pathlib import Path
import difflib
import json
import re
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *

def functions(text):
    found = {}
    for match in re.finditer(r'^(?:static )?(?:int32_t|uint32_t|unsigned|int|void|EngStatus)\s+(\w+)\([^;{}]*\)\s*\{', text, re.M):
        start = text.index('{', match.start())
        depth, end = 1, start + 1
        while depth:
            depth += (text[end] == '{') - (text[end] == '}')
            end += 1
        found[match.group(1)] = (text[match.start():end], text[:match.start()].count('\n') + 1)
    return found

def symbols(path):
    raw = path.read_bytes()
    h = struct.unpack_from('>16sHHIIIIIHHHHHH', raw)
    assert h[2] == 88  # EM_M32R
    sections = [struct.unpack_from('>10I', raw, h[6]+i*h[11]) for i in range(h[12])]
    found = {}
    for s in sections:
        if s[1] != 2:
            continue
        strings = sections[s[6]]
        names = raw[strings[4]:strings[4]+strings[5]]
        for offset in range(s[4], s[4]+s[5], s[9]):
            name, value, size, info, other, index = struct.unpack_from('>IIIBBH', raw, offset)
            name = names[name:].split(b'\0', 1)[0].decode()
            if info & 15 == 2 and size:
                found[name] = dict(address=value, size=size, section=index)
    return found

def main():
    layout_path = TREE / 'candidate/local/full-r13/layout.json'
    layout = json.loads(layout_path.read_text())
    sources = {name: file_sha(ROOT / name) == value for name, value in layout['sources'].items()}
    tools = {name: file_sha(ROOT / name) == value for name, value in layout['tools'].items()}
    assert all(sources.values()) and all(tools.values())
    raw = DAT.read_bytes()
    engine = (TREE / 'candidate/local/full-r13/engine.bin').read_bytes()
    assert raw[256:256 + len(engine)] == engine
    assert sha(engine) == layout['engine_sha256']
    reader = load(ROOT / 'tools/native_harness/image_loader.py', 'review_image_loader')
    elf = reader.Elf(ELF)
    section = next(x for x in elf.sections if x['name'] == '.engine')
    assert section['base'] == 256 and section['data'] == engine
    old_base = ROOT / 'firmware/engine_v43_fix/candidate'
    new_base = TREE / 'candidate'
    files = ['containers/product/adapter.c', 'containers/product/src/firmware/engine/core/eng_core.c',
             'containers/product/src/firmware/engine/core/eng_core.h',
             'containers/product/src/firmware/engine/panel/panel_ui.c', 'engine_services/services.c']
    diff = ''
    changed = []
    syms = symbols(ELF)
    inline = dict(list_bind_impl=['list_bind'], eng_require_recheck=['keep_view','deferred_menu','finish','ui_finish'],
                  eng_restore_cursor=['keep_view'], eng_display_current=['keep_view'], eng_menu_open=['ig_menu'],
                  eng_menu_deferred=['deferred_menu'], eng_retry_live=['retry_view'], rows=['panel_render'],
                  ui_list=['rv_call'])
    for name in files:
        before, after = (old_base / name).read_text(), (new_base / name).read_text()
        diff += ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                       fromfile='gen121/candidate/' + name, tofile='gen122/candidate/' + name))
        old, new = functions(before), functions(after)
        for fn, (body, line) in new.items():
            if fn in old and old[fn][0] == body:
                continue
            targets = inline.get(fn, [fn])
            resolved = []
            for target in targets:
                symbol = next((x for x in (target, target+'.constprop.0', target+'.lto_priv.0') if x in syms), None)
                assert symbol is not None, (fn, target)
                resolved.append(dict(symbol=symbol, **syms[symbol]))
            changed.append(dict(function=fn, file=str((new_base/name).relative_to(ROOT)), line=line,
                                source_sha256=sha(body.encode()), compiled=resolved, inlined=fn in inline))
    assert diff == (MATERIALS / 'source-change.patch').read_text()
    (OUT / 'local/source-change-reproduced.patch').write_text(diff)
    tool = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    command = [str(tool), '-d', '-z', str(ELF)]
    listing = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    (OUT / 'local/engine122.disasm').write_text(listing)
    direct = {}
    for row in changed:
        for target in row['compiled']:
            name, start, size = target['symbol'], target['address'], target['size']
            if name in direct:
                continue
            lines = []
            for line in listing.splitlines():
                match = re.match(r'\s*([0-9a-f]+):\s', line)
                if match and start <= int(match.group(1), 16) < start+size:
                    lines.append(line)
            text = '\n'.join(lines) + '\n'
            assert lines, name
            anomalies = [line for line in lines if any(x in line for x in ('.short', '.word', 'unknown', '(bad)'))]
            (OUT / 'local/compiled').mkdir(exist_ok=True)
            (OUT / 'local/compiled' / (name + '.txt')).write_text(text)
            direct[name] = dict(start=hex(start), end=hex(start+size), bytes=size,
                                instruction_lines=len(lines), sha256=sha(text.encode()),
                                embedded_data_or_decode_anomalies=[dict(pc=line.strip().split(':',1)[0],
                                    classification='pending embedded table classification') for line in anomalies])
    product = 'containers/product/src/firmware/engine/core/eng_core.c'
    old_core = functions((old_base/product).read_text())
    new_core = functions((new_base/product).read_text())
    unchanged = {name: old_core[name][0] == new_core[name][0] for name in
                 ('compute','deep','rpc','t_read','t_store','write_word','apply_impl','recover_confirmed','settings_match')}
    assert all(unchanged.values())
    # Validate exact map and all expanded recipe entries against gen 121.
    same = []
    base = BASE_DAT.read_bytes()
    for unit in range(3):
        d, old_d = struct.unpack_from('>I',raw,156)[0]+64*unit, struct.unpack_from('>I',base,156)[0]+64*unit
        m, om = struct.unpack_from('>I',raw,d+12)[0], struct.unpack_from('>I',base,old_d+12)[0]
        assert raw[m:m+152] == base[om:om+152]
        rows = []
        for j in range(9):
            address, length, offset = struct.unpack_from('>IHH', raw, m+32+12*j)
            first = address & 1
            assert first+2 <= length and offset+length <= 552 and address+length < 2**32
            rows.append(dict(row=j,address=hex(address),bytes=length,entry_offset=offset,
                             contained_halfwords=(length-first)//2,full_halfwords=(length+first+1)//2,
                             full_physical_start=hex(address & ~1),
                             full_physical_end=hex((address+length+1)&~1)))
        neighbor = struct.unpack_from('>I',raw,m+24)[0]
        assert neighbor == int(rows[1]['address'],16) + rows[1]['bytes'] - 1
        same.append(dict(unit=unit,map_identical=True,rows=rows,neighbor=hex(neighbor)))
    save('evidence/static-audit.json',dict(status='PASS_ARTIFACT_AND_DELTA_BINDING',
         dat_sha256=file_sha(DAT),elf_sha256=file_sha(ELF),body_sha256=file_sha(BODY),
         dat_engine_elf_equal=True,source_hashes=sources,tool_hashes=tools,
         patch_reproduced_exactly=True,changed_functions=changed,compiled_spans=direct,
         unchanged_write_and_compute_sources=unchanged,maps=same,
         command=command,scope='No compiler correctness claim follows solely from disassembly inventory.'))
    print(json.dumps(dict(status='PASS',changed_functions=len(changed),compiled_spans=len(direct),
                          engine_bytes=len(engine),source_files=len(sources))))

if __name__ == '__main__':
    main()
