"""Bind address evidence, the existing DAT and reference documents to hashes."""
import json
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

REFERENCES = (
    'research/recipes/sources/GXR_E.pdf',
    'research/recipes/sources/gxr_vup_en.pdf',
    'research/user_storage_r3/REPORT.md',
    'research/body_v4_storage/SYNTHESIS.md',
    'research/stage1_data/REPORT.md',
    'research/field_mapping/REPORT.md',
    'research/emulator_m2c/REPORT.md',
    'research/emulator_m2d/REPORT.md',
    'research/g135_v37/REPORT.md',
    'firmware/resident_v37/local/resident/size.json',
    'firmware/resident_v37/local/resident/build/resident.elf',
    'firmware/engine_v53_g135/candidate/local/full-r13/GXRCE.DAT',
    'firmware/engine_v53_g135/candidate/local/full-r13/engine.elf',
    'firmware/engine_v53_g135/candidate/local/full-r13/engine.bin',
    'firmware/engine_v53_g135/candidate/local/full-r13/layout.json',
    'firmware/engine_v53_g135/candidate/local/full-r13/manifest.json',
)


def elf_sections(path):
    raw = path.read_bytes()
    assert raw[:6] == bytes((127, 69, 76, 70, 1, 2))
    offset = struct.unpack_from('>I', raw, 32)[0]
    stride, count, names = struct.unpack_from('>3H', raw, 46)
    rows = [struct.unpack_from('>10I', raw, offset+stride*i) for i in range(count)]
    names = raw[rows[names][4]:rows[names][4]+rows[names][5]]
    return [(names[r[0]:].split(bytes(1), 1)[0].decode(), r[1], r[2], r[3], raw[r[4]:r[4]+r[5]])
            for r in rows]


def main():
    collect.preflight()
    refs = {name: dict(size=(collect.ROOT/name).stat().st_size, sha256=collect.sha(collect.ROOT/name))
            for name in REFERENCES}
    prior = collect.OUT/'reference-inputs.json'
    if prior.exists():
        assert json.loads(prior.read_text()) == refs, 'reference inputs changed'
    else:
        collect.save(prior.name, refs)
    p = collect.ROOT/'firmware/engine_v53_g135/candidate/local/full-r13'
    dat, code = (p/'GXRCE.DAT').read_bytes(), (p/'engine.bin').read_bytes()
    assert collect.sha(p/'GXRCE.DAT') == '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
    generation = struct.unpack_from('>I', dat, 28)[0]
    engine = next(r for r in elf_sections(p/'engine.elf') if r[0] == '.engine')
    assert generation == 135 and engine[3] == 256 and engine[4] == code
    assert dat[256:256+len(code)] == code
    body_path = collect.ROOT/'firmware/package_v37_g135/local/SD_ROOT/ilaunch3'
    body = body_path.read_bytes()
    im = collect.Image()
    resident = []
    for part, (name, kind, flags, address, raw) in enumerate(elf_sections(collect.ROOT/'firmware/resident_v37/local/resident/build/resident.elf')):
        if kind != 8 and flags & 2 and raw:
            offset = im.offset(address, len(raw))
            equal = body[offset:offset+len(raw)] == raw
            resident.append(dict(part=part, start=hex(address), size=len(raw), equal=equal))
            assert equal
    tail_default = im.raw(0x200d53c4+3364, 40)
    assert tail_default == bytes(40)
    fields = json.loads((collect.OUT/'s-fields.json').read_text())
    direct_tail = [r for r in fields if 0xfd4 <= int(r['offset'], 16) < 0xffc]
    assert not direct_tail
    pattern = re.compile(r'(?:@\((\d+),|(?:add3|ldi)\s+[^#]*#(\d+))')
    offset_candidates = []
    for address, raw, text, source, line in im.instructions():
        match = pattern.search(text)
        if match and 4052 <= int(match[1] or match[2]) < 4092:
            offset_candidates.append(dict(address=hex(address), text=text, source=source, line=line))
    windows = []
    for meta in sorted(collect.OUT.glob('*.meta.json')):
        row = json.loads(meta.read_text())
        assert collect.sha(meta.with_name(meta.name.removesuffix('.meta.json')+'.bin')) == row['sha256']
        for value in row['body_comparison'].values():
            assert value['changed_bytes'] == 0
        windows.append(dict(label=meta.name.removesuffix('.meta.json'), **row))
    manual = (collect.OUT/'body-manual.txt').read_text().split('\f')
    pages = [i for i, text in enumerate(manual, 1) if 'Start Settings Readout' in text
             and 'When the camera turns off' in text]
    assert pages == [162]
    result = dict(official_sha256=collect.EXPECTED, body_sha256=collect.sha(body_path),
        dat_sha256=collect.sha(p/'GXRCE.DAT'), dat_bytes=len(dat), generation=generation,
        engine_sha256=collect.sha(p/'engine.bin'), engine_elf_sha256=collect.sha(p/'engine.elf'),
        elf_engine_dat_equal=True, resident_sections=resident, windows=windows,
        tail=dict(start='S+0xfd4', end_exclusive='S+0xffc', capacity=40,
                  checksum_offset='S+0xffc', version_offset='S+0xe', current_version_length=3364,
                  extension_base='S+0x2b0', default_data_address='0x200d60e8',
                  default_zero=True, known_direct_field_references=0,
                  other_decimal_candidates=offset_candidates,
                  limits='Indexed tables, aliases and whole-range operations are not excluded.'),
        manual=dict(physical_page=162, printed_page=150, path=REFERENCES[0]),
        process_policy='Sequential commands; no child agents, camera, card or network.',
        writes='research/persist_recipe only')
    collect.save('facts.json', result)
    print(json.dumps(dict(dat_equal=True, resident_equal=True, windows=len(windows),
        tail_bytes=40, direct_tail_references=0, decimal_candidates=len(offset_candidates), manual_page=pages)))


if __name__ == '__main__':
    main()
