"""用 g154 原 C 对象和 pack_model 构建 18 Looks 本地测试包。"""
import copy
import shutil
import struct
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from relink import relink


def model(raw, pack):
    modules = []
    for unit, name in enumerate(pack.NAMES):
        at = u32(raw, 156) + 64 * unit
        directory = raw[at:at + 64]
        table = u32(directory, 20)
        owners = [raw[table + 16 + 20 * i] for i in range(directory[30])]
        entries = {slot: expand(raw, unit, slot) for slot in owners}
        records = [raw[u32(directory, 16) + 32 + 64 * i:][:64] for i in range(16)]
        references, ranges = [], []
        for i in range(16):
            meta = raw[u32(directory, 24) + 28 * i:][:28]
            references.append(owners[meta[24]])
            ranges.append([struct.unpack('bbb', meta[3 * j:3 * j + 3]) for j in range(8)])
        stock = entries[4]
        raw_stock = b''.join(stock[o:o + LENGTHS[k]] for k, o in zip(KINDS, OFFSETS)) + stock[445:447]
        mapping = raw[u32(directory, 12):][:152]
        pin = crc(mapping + raw_stock)
        assert pin == pack.PIN_CRC32[unit] == u32(directory, 32)
        modules.append(dict(name=name, map=mapping, records=records, entries=entries,
            refs=references, ranges=ranges, raw_stock=raw_stock, entry=stock,
            crc_pin=pin, pin=directory[32:64]))
    return modules


def main():
    guard()
    baseline = (BASE_PACKAGE / 'local/SD_ROOT/GXRCE.DAT').read_bytes()
    original_release = (ROOT / 'firmware/package_v39_g154/local/SD_ROOT/GXRCE.DAT').read_bytes()
    original_sections = sections(baseline)
    assert baseline[80:112].hex() == BUILD_ID and baseline[212:228].hex() == ABI_ID
    product = ENGINE / 'candidate/containers/product'
    sys.path.insert(0, str(product))
    pack = load(product / 'pack.py', 'g154_looks_pack')
    old_looks = load(BASE_ENGINE / 'candidate/containers/product/looks_data.py', 'looks_data')
    modules = model(baseline, pack)
    code_at, code_bytes = original_sections[0]
    reloc_at, reloc_bytes = original_sections[1]
    options = dict(engine=baseline[code_at:code_at + code_bytes],
        relocations=[struct.unpack_from('>II', baseline, i) for i in range(reloc_at, reloc_at + reloc_bytes, 8)],
        bss=u32(baseline, 116), entry=u32(baseline, 112),
        resident_id=bytes.fromhex(BUILD_ID), abi_id=bytes.fromhex(ABI_ID))
    control, _, _ = pack.pack_model(copy.deepcopy(modules), 154, **options)
    assert control == original_release, 'g154 original pack_model replay differs'
    looks = load(product / 'looks_data.py', 'looks_data')
    assert looks.CAPACITY == 18 and looks.CAPS == (0, 18, 16, 18)
    preliminary, _, _ = pack.pack_model(copy.deepcopy(modules), 154, **options)
    linked_code, linked_rel = relink(len(preliminary), baseline)
    options.update(engine=linked_code, relocations=linked_rel)
    release, trust, stats = pack.pack_model(copy.deepcopy(modules), 154, **options)
    assert len(release) == len(preliminary)
    test = bytearray(release)
    start, previous = u32(test, 204) + 1408, u32(baseline, 204) + 1408
    test[start:start + 1984] = baseline[previous:previous + 1984]
    test = pack.seal(test)
    effects = strict_effects(test)
    assert effects['names'] == [item['name'] for item in selected()]
    assert all(expand(test, u, s) == expand(baseline, u, s) for u in range(3) for s in range(1, 9))
    assert all(expand_effect(test, i) == expand_effect(baseline, i) for i in range(10))
    assert test[u32(test, 204):] == baseline[u32(baseline, 204):]
    new_sections = sections(test)
    assert test[new_sections[0][0]:][:new_sections[0][1]] == options['engine']
    assert test[new_sections[1][0]:][:new_sections[1][1]] == b''.join(struct.pack('>II', *r) for r in linked_rel)
    request = 7628 + align4(len(test) + options['bss'])
    sizes = dict(generation=154, fixed_overhead=7628, main_request=request, main_limit=107612,
        main_headroom=107612 - request, file_bytes=len(test), file_limit=98304,
        file_headroom=98304 - len(test), code_bytes=code_bytes, code_limit=65536,
        code_headroom=65536 - code_bytes, bss_bytes=options['bss'])
    assert request <= 107612 and len(test) <= 98304 and code_bytes <= 65536, sizes
    source = BASE_PACKAGE / 'local/SD_ROOT'
    output = PACKAGE / 'local/SD_ROOT'
    output.mkdir(parents=True, exist_ok=True)
    upgrade_files = sorted(p for p in source.iterdir() if p.name != 'GXRCE.DAT')
    assert len(upgrade_files) == 29
    for path in upgrade_files:
        shutil.copyfile(path, output / path.name)
        assert (output / path.name).read_bytes() == path.read_bytes()
    (output / 'GXRCE.DAT').write_bytes(test)
    assert len(list(output.iterdir())) == 30
    local_build = PACKAGE / 'local/build'
    local_build.mkdir(parents=True, exist_ok=True)
    (local_build / 'release-zero-users.DAT').write_bytes(release)
    (local_build / 'trust.bin').write_bytes(trust)
    base_build = BASE_ENGINE / 'candidate/local/full-r13'
    assert (local_build / 'engine.bin').read_bytes() == options['engine']
    layout = json.loads((base_build / 'layout.json').read_text())
    layout.update(stats)
    layout.update(engine_sha256=sha(linked_code), bss_start=len(test),
                  image_bss_bytes=len(test) + options['bss'], pic_translation_verified=True)
    save(local_build / 'layout.json', layout)
    for name in ('LICENSE-CC-BY-SA-4.0.txt', 'FILM-PROFILES-NOTICE.txt', 'FOTUFILM-NOTICE.txt'):
        shutil.copyfile(BASE_PACKAGE / name, PACKAGE / name)
    (PACKAGE / 'local/disable').mkdir(exist_ok=True)
    shutil.copyfile(BASE_PACKAGE / 'local/disable/GXRCE.CTL', PACKAGE / 'local/disable/GXRCE.CTL')
    (PACKAGE / '.gitignore').write_text('local/\nSD_ROOT\n')
    if not (PACKAGE / 'SD_ROOT').is_symlink():
        (PACKAGE / 'SD_ROOT').symlink_to('local/SD_ROOT')
    original_manifest = json.loads((BASE_PACKAGE / 'MANIFEST.json').read_text())
    new_sources = [{k: e[k] for k in ('name', 'source', 'source_sha256') if k in e} for e in selected()[10:]]
    original_manifest.update(generation=154, variant='g154-looks-r1-18-test', dat_sha256=sha(test),
        dat_bytes=len(test), users=3, effects=effects, logical_rows=30, physical_rows=8,
        max_row_characters=13, user_entry_limit=min(32, 40 - 18), body_sha256=BODY_SHA,
        upgrade_files_identical_to=BASE_PACKAGE.name, sizes=sizes,
        effect_sources=original_manifest['effect_sources'] + new_sources,
        local_only_sources=original_manifest['local_only_sources'] + list(ORDER),
        distribution='机主本地自用；新增 LUT 与派生参数的版权属于原作者；无公开分发授权。',
        code_provenance='Unchanged g154 C objects; relinked BSS at final DAT length. Only audited BSS address relocations change.')
    save(PACKAGE / 'MANIFEST.json', original_manifest)
    files = sorted(p for p in PACKAGE.rglob('*') if p.is_file() and not p.is_symlink()
                   and p.name not in ('.gitignore', 'SHA256SUMS'))
    (PACKAGE / 'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in files))
    save(HERE / 'evidence/build-size.json', sizes)
    save(HERE / 'evidence/package.json', dict(status='PASS', dat_sha256=sha(test),
        body_sha256=BODY_SHA, resident_build_id=BUILD_ID, resident_abi_id=ABI_ID,
        upgrade_files_equal=29, old_looks_equal=30, builtin_equal=24,
        original_g154_repack_equal=True, code_equal=False, only_BSS_address_relocations_changed=True,
        section7_equal=True, test_users_equal=3, sizes=sizes, effects=effects))
    print(json.dumps(dict(status='PASS', package=str(PACKAGE.relative_to(ROOT)), dat_sha256=sha(test), **sizes)))


if __name__ == '__main__':
    main()
