"""Compare instruction bytes while masking recorded linker relocations only."""
from pathlib import Path
import importlib.util
import json
import re
import struct

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
spec = importlib.util.spec_from_file_location('elf_mask', ROOT / 'firmware/stage2l_switch/tools/build.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def extract(gen):
    folder = 'engine_v37' if gen == 116 else 'engine_v38_ro'
    e = m.Elf(ROOT / ('firmware/' + folder + '/candidate/local/full-r13/engine.elf'))
    sec = next(s for s in e.sections if s['name'] == '.engine')
    data = bytearray(e.content(sec))
    rels = []
    for s in e.sections:
        if s['type'] != 4:
            continue
        syms = e.symbol_tables[s['link']]
        for pos in range(0, s['size'], 12):
            patch, info, addend = struct.unpack_from('>IIi', e.bytes, s['offset'] + pos)
            rels.append(dict(patch=patch, kind=info & 255, name=syms[info >> 8]['name'], addend=addend))
            if info & 255:
                off = patch - sec['va']
                kind = info & 255
                if kind in (2, 34):
                    data[off:off + 4] = bytes(4)
                elif kind in (48, 49):
                    data[off + 1:off + 4] = bytes(3)
                else:
                    data[off + 2:off + 4] = bytes(2)
    # Same-unit local calls are often resolved by the assembler and therefore
    # have no ELF relocation. Mask their encoded displacement symmetrically.
    for line in (OUT / ('relocated-' + str(gen) + '.dis')).read_text().splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.+)', line)
        if not match:
            continue
        pc, raw, asm = int(match[1], 16) - 0x21004000, bytes.fromhex(match[2]), match[3]
        if not re.search(r'\bbl\s+[0-9a-f]+', asm):
            continue
        off = pc - sec['va']
        if raw[0] == 0xfe:
            data[off + 1:off + 4] = bytes(3)
        else:
            for index, part in enumerate(re.split(r' -> | \|\| ', asm)):
                if part.startswith('bl '):
                    assert raw[2 * index] == 0x7e
                    data[off + 2 * index + 1] = 0
    return e, data, rels, sec


def main():
    a, b = extract(116), extract(117)
    names = ['eng_apply', 'eng_current', 'select_cached', 'ig_panel_open', 'ig_apply', 'list_bind',
             'rv_call', 't_read', 't_store', 'write_word', 'rpc.lto_priv.0', 'rpc.lto_priv.1',
             'a4_move', 'pn_ui_render.constprop.0', 'eng_visible_rows', 'es_session.constprop.0',
             'es_allocation', 'gxr2_semantic_validate', 'ig_init']
    rows = []
    for name in names:
        x, y = a[0].symbols[name], b[0].symbols[name]
        xb = a[1][x['value'] - a[3]['va']:x['value'] - a[3]['va'] + x['size']]
        yb = b[1][y['value'] - b[3]['va']:y['value'] - b[3]['va'] + y['size']]
        diff = [i for i, (u, v) in enumerate(zip(xb, yb)) if u != v]
        rows.append(dict(name=name, old_bytes=x['size'], new_bytes=y['size'], masked_identical=xb == yb,
                         nonrelocation_different_bytes=len(diff), differing_offsets=diff))
        print(name, x['size'], y['size'], 'relocation-only' if xb == yb else 'DIFFERENT', len(diff), diff[:24])
    (OUT / 'key-code-relocation-masked.json').write_text(json.dumps(rows, indent=2) + '\n')
    (OUT / 'relocations116.json').write_text(json.dumps(a[2], indent=2) + '\n')
    (OUT / 'relocations117.json').write_text(json.dumps(b[2], indent=2) + '\n')


if __name__ == '__main__':
    main()
