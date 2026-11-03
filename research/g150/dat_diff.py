"""g150 copy of research/g139m/dat_diff.py; only the output directory (research/g150/diff)
and the decode.py import path changed.

Section-by-section comparison of two gen 13x/14x GXRCE.DAT files (g139 vs g139m).

  dat_diff.py OLD.DAT OLD.elf NEW.DAT NEW.elf --label NAME

Read-only on its inputs; writes research/g150/diff/<label>.json. For each of
the 7 sections the differing bytes are classified:

  header    every differing byte is named (length, CRC, generation, section table);
  engine    every differing 32-bit word must be either an image-relative
            reference to BSS that moved by exactly the BSS_START shift (the
            DAT file length change), or one of the generation compare
            immediates (-old_gen -> -new_gen); anything else is UNEXPLAINED;
  relocs    compared by (patch, target) after the same BSS shift;
  directory per module: map/bank/table/tweak offsets, table length, entry count;
  maps      must be identical;
  banks     only the 16-bit build field and the header CRC per bank may differ;
  shared    decoded per unit and slot (rows, mask, control) via decode.py;
  tweaks    must be identical.
/usr/bin/python3 -I -B.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
G139M = HERE.parent / 'g139m'   # decode.py is imported read-only from there
ROOT = HERE.parents[1]
sys.path.insert(0, str(G139M))
import decode as D  # noqa: E402

u16 = lambda b, o: struct.unpack_from('>H', b, o)[0]
u32 = lambda b, o: struct.unpack_from('>I', b, o)[0]
NAMES = ('engine', 'relocs', 'directory', 'maps', 'banks', 'shared', 'tweaks')


def sections(raw):
    return [(u32(raw, 132 + 12 * i), u32(raw, 136 + 12 * i)) for i in range(7)]


def header_names(off):
    if 16 <= off < 20: return 'file length'
    if 20 <= off < 24: return 'header CRC'
    if 24 <= off < 28: return 'body CRC'
    if 28 <= off < 32: return 'generation'
    if 128 <= off < 212:
        i, k = divmod(off - 128, 12)
        return f'section {i + 1} ' + ('id' if k < 2 else 'flags' if k < 4 else 'offset' if k < 8 else 'length')
    return 'UNEXPLAINED'


def engine_words(old, new, shift, gens):
    """Classify every differing aligned word. shift = new BSS_START - old BSS_START."""
    rows = {'bss_reference': 0, 'generation_immediate': 0, 'unexplained': []}
    for at in range(0, len(old), 4):
        a, b = old[at:at + 4], new[at:at + 4]
        if a == b:
            continue
        ha, hb, la, lb = u16(a, 0), u16(b, 0), u16(a, 2), u16(b, 2)
        if ha == hb and (lb - la) & 0xffff == shift & 0xffff:
            rows['bss_reference'] += 1
        elif ha == hb and la == (-gens[0]) & 0xffff and lb == (-gens[1]) & 0xffff:
            rows['generation_immediate'] += 1
            rows.setdefault('generation_sites', []).append(hex(at))
        else:
            rows['unexplained'].append(dict(offset=hex(at), old=a.hex(), new=b.hex()))
    return rows


def symbols_check(old_elf, new_elf, bss_old, bss_new):
    """Every text symbol keeps its address; every BSS symbol moves by the shift."""
    E = D.load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'g139m_elf_reader').Elf
    a, b = E(old_elf).symbols, E(new_elf).symbols
    same = moved = 0; bad = []
    for name in sorted(set(a) | set(b)):
        if name not in a or name not in b:
            bad.append(dict(name=name, missing=True)); continue
        va, vb = a[name]['value'], b[name]['value']
        if va >= bss_old and vb == va - bss_old + bss_new and a[name]['size'] == b[name]['size']:
            moved += 1
        elif va == vb and a[name]['size'] == b[name]['size']:
            same += 1
        elif name in ('BSS_START',) or name.startswith('__'):
            same += 1
        else:
            bad.append(dict(name=name, old=hex(va), new=hex(vb)))
    return dict(same_address=same, moved_with_bss=moved, other=bad)


def unit_rows(raw):
    out = {}
    for m in D.modules(raw):
        out[m['name']] = dict(
            map=m['map'].hex(), records=[r.hex() for r in m['records']], refs=m['refs'],
            ranges=m['ranges'], pin=m['crc_pin'],
            slots={s: dict(mask=m['entries'][m['refs'][s - 1]][1], control=D.control(m['entries'][m['refs'][s - 1]]),
                           rows={k: v.hex() for k, v in D.rows(m['entries'][m['refs'][s - 1]]).items()})
                   for s in range(1, 17)})
    return out


def shared_diff(old, new):
    a, b = unit_rows(old), unit_rows(new)
    result = {}
    for unit in a:
        changes = []
        for key in ('map', 'records', 'refs', 'ranges', 'pin'):
            if a[unit][key] != b[unit][key]:
                changes.append(dict(field=key))
        for s in range(1, 17):
            x, y = a[unit]['slots'][s], b[unit]['slots'][s]
            fields = [k for k in ('mask', 'control') if x[k] != y[k]] + [k for k in x['rows'] if x['rows'][k] != y['rows'][k]]
            if fields:
                changes.append(dict(slot=s, fields=fields))
        result[unit] = changes
    return result, b


def main():
    p = argparse.ArgumentParser()
    p.add_argument('old'); p.add_argument('old_elf'); p.add_argument('new'); p.add_argument('new_elf')
    p.add_argument('--label', required=True)
    args = p.parse_args()
    old, new = Path(args.old).read_bytes(), Path(args.new).read_bytes()
    so, sn = sections(old), sections(new)
    gens = (u32(old, 28), u32(new, 28))
    shift = len(new) - len(old)
    out = dict(old=dict(path=args.old, sha256=hashlib.sha256(old).hexdigest(), bytes=len(old), generation=gens[0]),
               new=dict(path=args.new, sha256=hashlib.sha256(new).hexdigest(), bytes=len(new), generation=gens[1]),
               bss_start_shift=shift, sections={})
    hd = sorted({header_names(i) for i in range(256) if old[i] != new[i]})
    out['header'] = hd
    for i, name in enumerate(NAMES):
        (oo, ol), (no, nl) = so[i], sn[i]
        a, b = old[oo:oo + ol], new[no:no + nl]
        row = dict(old_offset=oo, new_offset=no, old_length=ol, new_length=nl, identical=a == b)
        if name == 'engine':
            row.update(engine_words(a, b, shift, gens))
        elif name == 'relocs':
            ra = [struct.unpack_from('>II', a, k) for k in range(0, len(a), 8)]
            rb = [struct.unpack_from('>II', b, k) for k in range(0, len(b), 8)]
            row['entries'] = [[hex(x), hex(y)] for x, y in ra]
            row['same_patch_sites'] = [x for x, _ in ra] == [x for x, _ in rb]
        elif name == 'directory':
            fields = []
            for k in range(ol):
                if a[k] != b[k]:
                    mi, f = divmod(k, 64)
                    label = next((n for lo, hi, n in ((12, 16, 'map offset'), (16, 20, 'bank offset'), (20, 24, 'table offset'),
                                                      (24, 28, 'tweak offset'), (28, 30, 'table length'), (30, 31, 'entry count'))
                                  if lo <= f < hi), f'UNEXPLAINED byte {f}')
                    fields.append(f'{D.pack.NAMES[mi]}: {label}')
            row['fields'] = sorted(set(fields))
        elif name == 'banks':
            fields = set()
            for k in range(ol):
                if a[k] != b[k]:
                    mi, f = divmod(k, 1056)
                    fields.add(f'{D.pack.NAMES[mi]}: ' + ('build field' if 16 <= f < 20 else 'bank header CRC' if 28 <= f < 32 else f'UNEXPLAINED byte {f}'))
            row['fields'] = sorted(fields)
        out['sections'][name] = row
    out['units'], decoded = shared_diff(old, new)
    out['symbols'] = symbols_check(args.old_elf, args.new_elf, len(old), len(new))
    target = HERE / 'diff' / (args.label + '.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(json.dumps(dict(label=args.label, header=hd, shift=shift,
                          sections={k: dict(identical=v['identical'], lengths=(v['old_length'], v['new_length']),
                                            **{x: v[x] for x in ('bss_reference', 'generation_immediate', 'unexplained', 'fields')
                                               if x in v}) for k, v in out['sections'].items()},
                          units=out['units'], symbols=dict(same=out['symbols']['same_address'],
                                                           moved=out['symbols']['moved_with_bss'],
                                                           other=out['symbols']['other'][:10])), indent=1))


if __name__ == '__main__':
    main()
