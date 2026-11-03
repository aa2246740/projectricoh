"""Independent ELF and relocated instruction inventories, from frozen artifacts."""
from pathlib import Path
import importlib.util
import hashlib
import json
import re
import struct
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
spec = importlib.util.spec_from_file_location('review_elf', ROOT / 'firmware/stage2l_switch/tools/build.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def extract(path):
    e = reader.Elf(path)
    section = next(s for s in e.sections if s['name'] == '.engine')
    data = e.content(section)
    symbols = {}
    for name, sym in e.symbols.items():
        if sym['info'] & 15 != 2 or not sym['size']:
            continue
        start = sym['value'] - section['va']
        symbols[name] = dict(size=sym['size'], address=hex(sym['value']),
                             bytes=data[start:start + sym['size']].hex())
    return e, data, symbols


def main():
    sources = {116: ROOT / 'firmware/engine_v37/candidate/local',
               117: ROOT / 'firmware/engine_v38_ro/candidate/local'}
    artifacts = {}
    for gen, folder in sources.items():
        e, data, symbols = extract(folder / 'full-r13/engine.elf')
        artifacts[gen] = (e, data, symbols)
        listing = subprocess.check_output([str(OBJDUMP), '-dr', str(folder / 'product-r13/m32r-lto/translated.elf')], text=True)
        (OUT / ('relocated-' + str(gen) + '.dis')).write_text(listing)
        (OUT / ('symbols-' + str(gen) + '.json')).write_text(json.dumps(symbols, indent=2) + '\n')
    old, new = artifacts[116][2], artifacts[117][2]
    rows = []
    for name in sorted(set(old) | set(new)):
        a, b = old.get(name), new.get(name)
        status = 'removed' if not b else 'added' if not a else 'identical' if a['bytes'] == b['bytes'] else 'changed'
        rows.append(dict(symbol=name, status=status, old_bytes=a['size'] if a else 0,
                         new_bytes=b['size'] if b else 0,
                         delta=(b['size'] if b else 0) - (a['size'] if a else 0)))
    (OUT / 'symbol-diff.json').write_text(json.dumps(rows, indent=2) + '\n')
    (OUT / 'symbol-diff.tsv').write_text('symbol\tstatus\told_bytes\tnew_bytes\tdelta\n' + ''.join(
        '\t'.join(str(row[k]) for k in ('symbol', 'status', 'old_bytes', 'new_bytes', 'delta')) + '\n' for row in rows))
    print('engine sizes', {gen: len(x[1]) for gen, x in artifacts.items()})
    print('symbol counts', {gen: len(x[2]) for gen, x in artifacts.items()})
    print('status counts', {s: sum(x['status'] == s for x in rows) for s in ('removed', 'added', 'identical', 'changed')})
    print('Every shrink/removal:')
    for row in rows:
        if row['delta'] < 0:
            print(row['symbol'], row['old_bytes'], row['new_bytes'], row['delta'])


if __name__ == '__main__':
    main()
