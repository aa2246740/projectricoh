#!/usr/bin/env python3
"""Generate Canonical defaults, source-bound ISP rows and package DAT inputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
RESEARCH = ROOT / 'research/stage2a_deep_isp'
CANON = ROOT / 'research/canonical_gr_pack'
PROFILES = (1, 2, 3, 5)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load_make():
    spec = importlib.util.spec_from_file_location('canonical_make', HERE/'tools/make_recipes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def array(name, blob):
    return 'static const uint8_t ' + name + '[] = {\n' + ''.join(
        '    ' + ','.join(f'0x{x:02x}' for x in blob[i:i+16]) + ',\n'
        for i in range(0, len(blob), 16)) + '};\n'


def checked(record, fmt):
    blob = bytes.fromhex(record['hex'])
    assert len(blob) == record['bytes'] and sha(blob) == record['sha256']
    assert blob == struct.pack('>' + fmt * len(record['values']), *record['values'])
    if 'source_path' in record:
        path = Path(record['source_path'])
        assert not str(path).startswith('/Volumes/')
        native = path.read_bytes()
        assert sha(native) == '23c4d8b2307ce4acc6dc33a5f896d506ffef1815ad999013900e8e9908d1c337'
        start = int(record['source_file_offset'], 16)
        assert native[start:start+len(blob)] == blob
    return blob


def documents():
    canonical = json.loads((CANON/'canonical_16_slots.json').read_text())
    surface = dict(format_version=2, generation=1,
                   recipes=[s['surface_fallback'] for s in canonical['slots']])
    assert surface == json.loads((CANON/'stage1c_v2_recipes.json').read_text())
    assert [s['slot'] for s in surface['recipes']] == list(range(1, 17))
    deep = copy.deepcopy(surface)
    # Gate 2 proves the common A5/B5 only at native display contrast 5.
    # Applying the fallback contrast 3/9/8 would select a different still row.
    for entry in deep['recipes']:
        if entry['slot'] in PROFILES:
            entry['parameters']['contrast'] = 5
    legacy = copy.deepcopy(surface)
    legacy['format_version'] = 1
    make = load_make()
    for entry in legacy['recipes']:
        mode = entry.pop('base_mode')
        if mode != 'color':
            controls = {p: 5 for p in make.PARAMETERS}
            controls.update(contrast=entry['parameters']['contrast'],
                            sharpness=entry['parameters']['sharpness'], vividness=1)
            entry['parameters'] = controls
    return canonical, surface, deep, legacy


def main():
    canonical, surface, deep, legacy = documents()
    make = load_make()
    safe_blob = make.compile_recipes(surface)
    deep_blob = make.compile_recipes(deep)
    for name in ('RECIPE20.DAT', 'RECIPE21.DAT'):
        assert safe_blob == (CANON/name).read_bytes()
    for name, doc in [('canonical_surface.json', surface), ('deep_inputs.json', deep),
                      ('canonical_v1_fallback.json', legacy)]:
        (HERE/'examples'/name).write_text(json.dumps(doc, indent=2)+'\n')
    for name, blob in [('RECIPE20.DAT', safe_blob), ('RECIPE21.DAT', safe_blob),
                       ('DEEPISP0.DAT', deep_blob), ('DEEPISP1.DAT', deep_blob),
                       ('RECIPES0.DAT', make.compile_recipes(legacy))]:
        (HERE/'examples'/name).write_bytes(blob)

    image = (ROOT/'artifacts/firmware/gxr-1.51/jlaunch3').read_bytes()
    assert sha(image) == '951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673'
    segments = [struct.unpack_from('>5I', image, 32+i*20) for i in range(16)]
    def read(va, count):
        hits = [src+512+va-base for src,base,size,_,_ in segments if base <= va and va+count <= base+size]
        assert len(hits) == 1
        return image[hits[0]:hits[0]+count]

    tables = json.loads((CANON/'deep_isp_tables.json').read_text())
    data = [[read(0x2012f504, 62), read(0x2012fffc, 33), read(0x2012c5d4, 96)]]
    source_records = []
    for slot in PROFILES:
        entry = tables['slots'][f'{slot:02d}']
        tone = entry['type26']
        a = checked(tone['input31_u16BE'], 'H')
        b = checked(tone['output33'], 'B')
        if slot == 2:
            color = entry['type28_alternatives']['chroma_only']['type28_main24_u32BE']
        elif slot == 3:
            color = None  # HC uses true 03 grayscale, retain stock color row1.
        else:
            color = entry['type28']['main24_u32BE']
        c = checked(color, 'I') if color else data[0][2]
        assert tuple(map(len, (a,b,c))) == (62,33,96)
        data.append([a,b,c])
        source_records.append(dict(slot=slot, name=deep['recipes'][slot-1]['name'],
            tone_source_row=tone.get('source_row_1based'),
            color_source_row=entry['type28']['main_row_1based'] if entry['type28'] else None,
            tone_source='GR III GammaTuning projection' if slot == 2 else 'GR DIGITAL IV exact native bytes',
            color_policy='chroma_only' if slot == 2 else 'stock color, native 03 grayscale' if slot == 3 else 'exact native row',
            a5_sha256=sha(a), b5_sha256=sha(b), color_sha256=sha(c)))
    text = '#include "deep_isp.h"\n/* Generated by tools/generate_deep_tables.py; see package_tables.json. */\n'
    text += '#if RFW_DEEP_ENABLED\n#define DEEP_CONTRAST(surface) 3\n#else\n#define DEEP_CONTRAST(surface) surface\n#endif\n'
    text += 'const Rv1Recipe rfw_defaults[RV1_SLOT_COUNT] = {\n'
    for i, entry in enumerate(surface['recipes']):
        record = safe_blob[32+i*64:96+i*64]
        raw = [str(v) for v in record[36:49]]
        if i+1 in PROFILES:
            raw[0] = f'DEEP_CONTRAST({raw[0]})'
        text += ('    {' + f'{record[2]},{json.dumps(entry["name"])},{record[3]},' +
                 '{'+','.join(raw)+'},{'+','.join(map(str,entry['wb']))+'}},\n')
    text += '};\n#if RFW_DEEP_ENABLED\n'
    text += 'const uint8_t rfw_deep_slots[RFW_DEEP_PROFILES] = {1,2,3,5};\n'
    names = {}
    for profile, rows in enumerate(data):
        for row, blob in enumerate(rows):
            if blob not in names:
                name = f'table_{profile}_{row}'
                names[blob] = name
                text += array(name, blob)
    text += 'const RfwDeepRow rfw_deep_rows[RFW_DEEP_ROWS] = {\n'
    records = []
    for row, (address, length) in enumerate(((0x2012f504,62),(0x2012fffc,33),(0x2012c5d4,96))):
        text += f'    {{{address:#x},{length},'+'{'+','.join(names[rows[row]] for rows in data)+'}},\n'
        records.append(dict(address=hex(address), bytes=length,
            profiles=[dict(id=i, hex=rows[row].hex(), sha256=sha(rows[row])) for i,rows in enumerate(data)]))
    text += '};\n#endif\n'
    (HERE/'deep_tables.c').write_text(text)
    manifest = dict(schema='stage2a-canonical-tables-v1', profiles=source_records, rows=records,
        input_sha256={str((CANON/name).relative_to(ROOT)):sha((CANON/name).read_bytes()) for name in
                      ('canonical_16_slots.json','deep_isp_tables.json','RECIPE20.DAT','RECIPE21.DAT','calibration_current.json')},
        jlaunch3_sha256=sha(image), camera_validation='NOT_RUN',
        safe_surface_identical_to_canonical_DAT=True,
        diagnostic_calibration=canonical['calibration'],
        control_refinements='Canonical surface fallback kept exactly; no calibrated per-control response exists.',
        deep_carrier_override=dict(slots=list(PROFILES), contrast_display=5, raw=3,
            reason='Gate 2 common A5/B5 source at native contrast 5; avoid fallback contrast selecting another row'),
        neighbor=dict(halfword_address='0x2013001c', preserved_byte_address='0x2013001d',
                      capture='once per resident session before first W', from_live_RAM=True),
        rpc_counts=dict(first_transfer=104, later_transfer=102, first_V=4, later_V=3, W=96),
        legacy_v1=dict(all_slots_color_only=True, native_03_06_supported=False,
                       monochrome_fallback='C/S preserved, vividness display1; not true grayscale or TE'),
        dat_sha256={name:sha((HERE/'examples'/name).read_bytes()) for name in
                    ('RECIPE20.DAT','RECIPE21.DAT','DEEPISP0.DAT','DEEPISP1.DAT','RECIPES0.DAT')})
    (RESEARCH/'package_tables.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(profiles=4, unique_tables=len(names), unique_table_bytes=sum(map(len,names)),
                          surface_sha256=sha(safe_blob), deep_sha256=sha(deep_blob))))


if __name__ == '__main__':
    main()
