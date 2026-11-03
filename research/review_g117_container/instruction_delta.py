"""Explain call relaxation and bundling separately from raw byte identity."""
from pathlib import Path
import bisect
import difflib
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
symbols = {g: json.loads((OUT / f'symbols-{g}.json').read_text()) for g in (116, 117)}
by_bytes = {}
for items in symbols.values():
    for name, row in items.items():
        by_bytes.setdefault(row['bytes'], set()).add(name)
aliases = {name: min(names, key=lambda n: (len(n), n)) for names in by_bytes.values() for name in names}


def parse(gen):
    instructions, relocs = {}, {}
    for line in (OUT / f'relocated-{gen}.dis').read_text().splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.+)', line)
        if m:
            instructions[int(m[1], 16)] = (bytes.fromhex(m[2]), m[3])
        m = re.match(r'\s*([0-9a-f]+): (R_M32R_[A-Z0-9_]+)', line)
        if m:
            relocs[int(m[1], 16)] = m[2]
    return instructions, relocs


def normalize(gen, name):
    instructions, relocs = parse(gen)
    symbol = symbols[gen][name]
    begin = int(symbol['address'], 16) + 0x21004000
    end = begin + symbol['size']
    flat = []
    for pc, (raw, asm) in sorted(instructions.items()):
        if begin <= pc < end:
            for index, part in enumerate(re.split(r' -> | \|\| ', asm)):
                if part != 'nop':
                    flat.append((pc + 2 * index, part, relocs.get(pc)))
    pcs = [pc for pc, _, _ in flat]
    result = []
    for pc, asm, reloc in flat:
        if reloc and any(x in reloc for x in ('GOTOFF', 'GOTPC', 'GOT16')):
            asm = re.sub(r'#[^, ]+$', '#LINK', asm)
        match = re.search(r'\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bltz|bgtz|blez)\s+.*?([0-9a-f]{6,}) <([^>]+)>', asm)
        if match:
            address = int(match[2], 16)
            if begin <= address < end:
                target = 'self@' + str(bisect.bisect_left(pcs, address))
            else:
                target = re.sub(r'(?:\.lto_priv\.\d+)+', '', aliases.get(match[3], match[3]))
            asm = asm[:match.start(2)] + target
        else:
            # objdump labels immediate constants against its nearest symbol.
            asm = re.sub(r' <[^>]+>', '', asm)
        result.append(asm)
    return result


names = ['eng_apply', 'eng_current', 'select_cached', 'ig_panel_open', 'ig_apply', 'list_bind',
         'rv_call', 't_read', 't_store', 'write_word', 'rpc.lto_priv.0', 'rpc.lto_priv.1',
         'a4_move', 'pn_ui_render.constprop.0', 'eng_visible_rows', 'es_session.constprop.0',
         'es_allocation', 'gxr2_semantic_validate', 'ig_init']
rows, patch = [], []
for name in names:
    a, b = normalize(116, name), normalize(117, name)
    equal = a == b
    rows.append(dict(name=name, normalized_equal=equal, old_instructions=len(a), new_instructions=len(b),
                     normalization='recorded address immediates, symbolic branch/call targets, proven byte-identical helper aliases, NOP/packet layout'))
    patch.extend(difflib.unified_diff(a, b, fromfile='116/' + name, tofile='117/' + name, lineterm=''))
    print(name, 'normalized equal' if equal else 'DELTA', len(a), len(b))
(OUT / 'instruction-delta.json').write_text(json.dumps(rows, indent=2) + '\n')
(OUT / 'instruction-delta.patch').write_text('\n'.join(patch) + '\n')
