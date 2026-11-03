"""Independently bind the two source deltas and all 48 decoded DAT entries."""
from pathlib import Path
import difflib
import json
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *
from static_audit import functions

U16 = lambda b, o: struct.unpack_from('>H', b, o)[0]
U32 = lambda b, o: struct.unpack_from('>I', b, o)[0]
OFFSETS = (20, 82, 115, 216, 284, 346, 379, 412, 456, 518)
SIZES = (62, 33, 96, 56, 62, 33, 33, 33, 62, 33)
KINDS = (0, 1, 2, 3, 0, 1, 1, 1, 0, 1)


def decode(raw, unit):
    d = U32(raw, 156) + 64 * unit
    shared = U32(raw, 192)
    table, meta = U32(raw, d + 20), U32(raw, d + 24)
    mapping = raw[U32(raw, d+12):U32(raw, d+12)+152]
    owners, entries = [], {}
    for i in range(raw[table + 5]):
        desc = raw[table+16+20*i:table+36+20*i]
        owners.append(desc[0])
        e = bytearray(552)
        e[:2], e[4:8], e[445:447] = desc[:2], desc[4:8], desc[2:4]
        for off, size, kind, index in zip(OFFSETS, SIZES, KINDS, desc[8:18]):
            pool = shared + 16 + 12*kind
            assert U16(raw, pool+2) == size
            assert index < U16(raw, pool)
            at = shared + U32(raw, pool+4) + index*size
            assert at + size <= len(raw)
            e[off:off+size] = raw[at:at+size]
        for off, size, crc_off in ((20,62,8),(82,33,12),(115,96,16),(216,56,212),
                                  (284,62,272),(346,33,276),(379,66,280),
                                  (456,62,448),(518,33,452)):
            struct.pack_into('>I', e, crc_off, zlib.crc32(e[off:off+size]))
        entries[desc[0]] = bytes(e)
    expanded, effective = [], []
    for i in range(16):
        assert raw[meta+28*i+24] < len(owners)
        e = entries[owners[raw[meta+28*i+24]]]
        expanded.append(e)
        rows = []
        for j in range(9):
            r = mapping[32+12*j:44+12*j]
            size, off, flag = U16(r, 4), U16(r, 6), r[10]
            assert off + size <= 552
            source = entries[4] if flag and not(e[1] & flag) else e
            rows.append(source[off:off+size])
        effective.append(b''.join(rows) + e[445:447])
    return dict(mapping=mapping, expanded=expanded, effective=effective,
                records=raw[U32(raw,d+16)+32:U32(raw,d+16)+1056],
                metadata=raw[meta:meta+16*28])


def check_patch(old, name):
    patch = (MATERIALS / name).read_text()
    paths = [line[len('+++ gen123/'):] for line in patch.splitlines()
             if line.startswith('+++ gen123/')]
    reproduced = ''
    for path in paths:
        before = (old / path).read_text() if (old / path).exists() else ''
        after = (TREE / path).read_text()
        reproduced += ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
            fromfile='gen' + ('121' if '121' in name else '122') + '/' + path,
            tofile='gen123/' + path))
    assert reproduced == patch, name
    (OUT / 'local' / name).write_text(reproduced)
    return paths


def main():
    raw, base = DAT.read_bytes(), BASE_DAT.read_bytes()
    assert file_sha(DAT) == PIN
    result = dict(dat_sha256=sha(raw), base_sha256=sha(base), units=[], source={})
    for oldgen, tree in ((121, 'engine_v43_fix'), (122, 'engine_v44_keep')):
        old = ROOT / 'firmware' / tree
        name = f'source-change-vs-g{oldgen}.patch'
        patch_paths = check_patch(old, name)
        changes = []
        for part in ('containers/product', 'engine_services'):
            directory = TREE/'candidate'/part
            paths = {p.relative_to(TREE/'candidate') for p in directory.rglob('*')
                     if p.is_file() and 'local' not in p.relative_to(directory).parts
                     and p.suffix in ('.c', '.h', '.S', '.ld')}
            prior = old/'candidate'/part
            paths.update(p.relative_to(old/'candidate') for p in prior.rglob('*')
                         if p.is_file() and 'local' not in p.relative_to(prior).parts
                         and p.suffix in ('.c', '.h', '.S', '.ld'))
            for path in sorted(paths):
                a, b = old/'candidate'/path, TREE/'candidate'/path
                if a.read_bytes() != b.read_bytes():
                    assert 'candidate/'+str(path) in patch_paths, path
                    fa, fb = functions(a.read_text()), functions(b.read_text())
                    changes.append(dict(file=str(path), added=sorted(set(fb)-set(fa)),
                        removed=sorted(set(fa)-set(fb)),
                        changed=[fn for fn in fb if fn in fa and fa[fn][0] != fb[fn][0]]))
        result['source'][str(oldgen)] = dict(patch_exact=True, source_changes=changes,
            other_patch_paths=[x for x in patch_paths if x not in
                               ['candidate/'+y['file'] for y in changes]])
    for unit in range(3):
        a, b = decode(raw, unit), decode(base, unit)
        assert a == b, unit
        name = ('jlaunch', 'qlaunch', 'l08firm')[unit]
        for i, entry in enumerate(a['expanded'], 1):
            for tree in (TREE, ROOT/'firmware/engine_v43_fix'):
                saved = tree/'candidate/local/full-r13/expanded'/name/f'{i:02}.entry'
                assert saved.read_bytes() == entry, saved
        result['units'].append(dict(unit=('50mm','28mm','mount')[unit],
            entries=16, expanded_sha256=[sha(x) for x in a['expanded']],
            effective_sha256=[sha(x) for x in a['effective']],
            mapping_identical=True, records_identical=True, metadata_identical=True,
            expanded_entries_identical=True, effective_rows_and_T_identical=True))
    # Classify every non-engine DAT difference, including reserved fields.
    normalized_header, old_header = bytearray(raw[:256]), bytearray(base[:256])
    for start, length in [(16,16),(112,8),*[(132+12*i,4) for i in range(7)],(136,4)]:
        normalized_header[start:start+length] = bytes(length)
        old_header[start:start+length] = bytes(length)
    assert normalized_header == old_header
    relocation_semantics=[]
    for data, label, tree in ((raw,'123',TREE),(base,'121',ROOT/'firmware/engine_v43_fix')):
        reloc_start, reloc_bytes = U32(data,144), U32(data,148)
        assert reloc_bytes == 8
        patch,target=struct.unpack_from('>II',data,reloc_start)
        assert patch%4==0 and 256<=patch<=256+U32(data,136)-4
        assert 256<=target<len(data)+U32(data,116)
        assert U32(data,patch)==target
        from static_audit import symbols
        obj=next((name for name,info in symbols(tree/'candidate/local/full-r13/engine.elf').items()
                  if info['address']==target),None)
        assert obj=='rv_call',obj
        relocation_semantics.append(dict(generation=label,target_symbol=obj))
    directory_pointer_delta=[]
    for unit in range(3):
        d,old_d=U32(raw,156)+64*unit,U32(base,156)+64*unit
        current,prior=bytearray(raw[d:d+64]),bytearray(base[old_d:old_d+64])
        deltas=[]
        for offset in (12,16,20,24):
            deltas.append(U32(current,offset)-U32(prior,offset))
            current[offset:offset+4]=prior[offset:offset+4]=bytes(4)
        assert current==prior and deltas==[len(raw)-len(base)]*4
        directory_pointer_delta.append(dict(unit=unit,delta=deltas[0]))
    result.update(normalized_header_identical=True,relocation_semantics=relocation_semantics,
                  directory_pointer_changes_only=directory_pointer_delta)
    parts = []
    for i in range(7):
        x, n = U32(raw,132+12*i), U32(raw,136+12*i)
        y, m = U32(base,132+12*i), U32(base,136+12*i)
        same = raw[x:x+n] == base[y:y+m]
        parts.append(dict(part=i+1, bytes=n, base_bytes=m, identical=same))
        if i in (3,5,6):
            assert same, i
        if i == 4:
            for unit in range(3):
                bank, prior = bytearray(raw[x+1056*unit:x+1056*(unit+1)]), bytearray(base[y+1056*unit:y+1056*(unit+1)])
                # The bank header contains its generation and CRC only;
                # recipe records were independently compared above.
                result.setdefault('bank_headers', []).append(dict(unit=unit,
                    changed_offsets=[j for j in range(32) if bank[j] != prior[j]]))
                assert U32(bank,16)==123 and U32(prior,16)==121
                bank[16:20]=prior[16:20]=bytes(4)
                bank[28:32]=prior[28:32]=bytes(4)
                assert bank==prior
    result['dat_parts'] = parts
    fixed = []
    package = DAT.parent
    reference = ROOT/'firmware/package_v36_g120b/SD_ROOT'
    for p in sorted(package.rglob('*')):
        if p.is_file() and p != DAT:
            rel = p.relative_to(package)
            assert p.read_bytes() == (reference/rel).read_bytes(), rel
            fixed.append(str(rel))
    assert len(fixed) == 29
    result.update(status='PASS', expanded_entries=48, fixed_files_equal_gen120b=fixed)
    save('evidence/delta-audit.json', result)
    print('PASS both source patches; 48 exact expanded entries and effective rows; 29 fixed package files')


if __name__ == '__main__':
    main()
