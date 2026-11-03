"""按新 DAT 文件长度重链接 g154 原对象，检查全部地址变化。"""
import os
import shutil
import struct
import subprocess
from common import *


def relink(total, baseline):
    guard()
    commands = [json.loads(line) for line in (BASE_ENGINE / 'candidate/local/commands.jsonl').read_text().splitlines()]
    template = [row['argv'] for row in commands if row['label'] == 'm32r-lto-oz-engine'][-1]
    reader = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'g154_looks_elf_reader')
    work = TMP / 'relink'
    work.mkdir(parents=True, exist_ok=True)
    runs = []

    def link(length, label, address=0):
        folder = work / label
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'engine.elf'
        args = list(template)
        for i, value in enumerate(args):
            if value.startswith('-Wl,--defsym=BSS_START='):
                args[i] = '-Wl,--defsym=BSS_START=' + str(length)
            elif value.startswith('-Wl,--defsym=IMAGE_BASE='):
                args[i] = '-Wl,--defsym=IMAGE_BASE=' + str(address)
            elif value.startswith('-Wl,-Map='):
                args[i] = '-Wl,-Map=' + str(folder / 'engine.map')
            elif value == '-Wl,' + str(BASE_ENGINE / 'candidate/containers/product/engine.ld'):
                args[i] = '-Wl,' + str(ENGINE / 'candidate/containers/product/engine.ld')
        args[args.index('-o') + 1] = str(output)
        proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10800,
                              env=dict(os.environ, TMPDIR=str(work), CLANG_MODULE_CACHE_PATH=str(work / 'clang')))
        (HERE / 'evidence' / ('link-' + label + '.log')).write_text(proc.stdout + proc.stderr)
        runs.append(dict(label=label, argv=args, returncode=proc.returncode))
        proc.check_returncode()
        return reader.Elf(output), output

    def section(elf, name):
        return next(s for s in elf.sections if s['name'] == name)

    def relocations(elf):
        blob = elf.content(section(elf, '.engine'))
        result = []
        for sec in elf.sections:
            if sec['type'] != 4:
                continue
            for at in range(0, sec['size'], 12):
                patch, info, addend = struct.unpack_from('>IIi', elf.bytes, sec['offset'] + at)
                kind = info & 255
                assert kind in (0, 2, 34, 48, 49, 60, 61, 63, 64), kind
                if kind in (2, 34):
                    result.append((patch, u32(blob, patch - 256)))
        return sorted(set(result))

    def static_relocations(elf):
        result = []
        for sec in elf.sections:
            if sec['type'] != 4:
                continue
            syms = elf.symbol_tables[sec['link']]
            for at in range(0, sec['size'], 12):
                patch, info, addend = struct.unpack_from('>IIi', elf.bytes, sec['offset'] + at)
                symbol = syms[info >> 8]
                result.append(dict(patch=patch, kind=info & 255, addend=addend,
                    symbol=symbol['name'], value=symbol['value'], section=symbol['section']))
        return result

    base_at, base_size = sections(baseline)[0]
    base_code = baseline[base_at:base_at + base_size]
    old_at, old_size = sections(baseline)[1]
    old_rel = [struct.unpack_from('>II', baseline, at) for at in range(old_at, old_at + old_size, 8)]
    control, _ = link(len(baseline), 'baseline-control')
    assert control.content(section(control, '.engine')) == base_code
    assert relocations(control) == old_rel
    linked, path = link(total, 'final')
    translated, _ = link(total, 'translated', 0x21004000)
    code = linked.content(section(linked, '.engine'))
    rel = relocations(linked)
    bss = section(linked, '.bss')
    assert bss['va'] == total and bss['size'] == u32(baseline, 116)
    assert len(code) == base_size and len(rel) == len(old_rel)
    delta = total - len(baseline)
    expected = bytearray(base_code)
    changed = []
    for (old_patch, old_target), (patch, target) in zip(old_rel, rel):
        assert patch == old_patch
        wanted = old_target + delta if old_target >= len(baseline) else old_target
        assert target == wanted and 256 <= target < total + bss['size']
        struct.pack_into('>I', expected, patch - 256, target)
        if target != old_target:
            changed.append(dict(patch=patch, previous_target=old_target, target=target))
    # M32R also resolves PIC BSS references as GOT-relative instruction immediates.
    # Kind 64 is R_M32R_GOTOFF_SLO. Its low 16 bits shift with BSS_START.
    static_old, static_new = static_relocations(control), static_relocations(linked)
    assert len(static_old) == len(static_new)
    changed_gotoff = []
    for old, new in zip(static_old, static_new):
        assert {k: v for k, v in old.items() if k != 'value'} == {k: v for k, v in new.items() if k != 'value'}
        if new['section'] != bss['index']:
            assert new['value'] == old['value']
            continue
        assert new['value'] == old['value'] + delta
        if new['kind'] == 64:
            offset = new['patch'] - 256
            before = u32(base_code, offset)
            wanted = (before & 0xffff0000) | ((before + delta) & 0xffff)
            assert u32(code, offset) == wanted
            struct.pack_into('>I', expected, offset, wanted)
            changed_gotoff.append(dict(patch=new['patch'], addend=new['addend'],
                                       previous_value=old['value'], value=new['value']))
    assert bytes(expected) == code, 'changes outside audited BSS address relocations'
    translated_code = bytearray(translated.content(section(translated, '.engine')))
    for patch, target in rel:
        assert u32(translated_code, patch - 256) == 0x21004000 + target
        struct.pack_into('>I', translated_code, patch - 256, target)
    assert bytes(translated_code) == code
    bss_symbols = [s for s in linked.symbols.values() if s['section'] == bss['index']]
    assert bss_symbols
    for symbol in bss_symbols:
        assert total <= symbol['value'] and symbol['value'] + symbol['size'] <= total + bss['size'], symbol
    for name in ('n', 'g'):
        symbols = [s for s in bss_symbols if s['name'] == name or s['name'].startswith(name + '.')]
        assert len(symbols) == 1, name
    output = PACKAGE / 'local/build'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, output / 'engine.elf')
    shutil.copyfile(path.with_suffix('.map'), output / 'engine.map')
    (output / 'engine.bin').write_bytes(code)
    (output / 'reloc.bin').write_bytes(b''.join(struct.pack('>II', *r) for r in rel))
    receipt = dict(status='PASS', source_C_unchanged=True, original_link_control_equal=True,
        code_bytes=len(code), bss_start=bss['va'], bss_bytes=bss['size'],
        image_bss_end=total + bss['size'], delta=delta, changed_BSS_pointer_cells=changed,
        changed_BSS_GOTOFF_SLO=changed_gotoff,
        changed_code_bytes=sum(a != b for a, b in zip(base_code, code)),
        only_BSS_address_relocations_changed=True, pic_translation_verified=True,
        bss_symbols_within_allocation=True, code_sha256=sha(code), relocations=len(rel),
        object_inputs={p: sha(Path(p).read_bytes()) for p in template if p.endswith(('.o', '.a'))},
        runs=runs)
    save(HERE / 'evidence/relink.json', receipt)
    return code, rel
