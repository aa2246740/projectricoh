#!/usr/bin/env python3
"""Recover shipped parameter words and byte-verified M32R evidence. No device I/O."""
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FW = ROOT / 'artifacts/firmware/gxr-1.51'
DIS = ROOT / 'research/tooling_m32r/disasm'
DISPLAY_TO_RAW = [7, 6, 1, 2, 3, 4, 5, 8, 9]
COLORS = ['orange', 'green', 'blue', 'red', 'magenta']


def save(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main():
    firmware = (FW / 'jlaunch3').read_bytes()
    sections = [(o + 512, v, n) for o, v, n, _, _ in
                (struct.unpack_from('>IIIII', firmware, 32 + i * 20) for i in range(16))]

    def offset(va):
        for o, v, n in sections:
            if v <= va < v + n:
                return o + va - v
        raise ValueError(f'Unmapped VMA: {va:#x}')

    def read(va, n):
        o = offset(va)
        assert offset(va + n - 1) == o + n - 1
        return firmware[o:o + n]

    def jump(va, base, n):
        return [base + x for x in struct.unpack('>' + str(n) + 'h', read(va, n * 2))]

    # V selects a byte offset; W supplies a big-endian u16. The control domain
    # UEEF1 is preserved as evidence, not executed or claimed as a live dump.
    script = (FW / 'jlaunch8').read_bytes()
    sparse, origins, writes, controls = {}, {}, [], []
    addr, domain = None, None
    file_offset = 512
    for no, line in enumerate(script[512:].splitlines(keepends=True), 1):
        token = line.strip().decode('latin1')
        m = re.fullmatch(r'([XVWU])([0-9a-fA-F]{4})', token)
        if m:
            command, value = m[1], int(m[2], 16)
            if command == 'U':
                domain = value
                controls.append({'line': no, 'file_offset': hex(file_offset), 'command': token})
            elif command == 'X':
                controls.append({'line': no, 'file_offset': hex(file_offset), 'command': token})
            elif command == 'V':
                addr = value
            elif command == 'W':
                assert addr is not None and domain == 0xEEF1
                writes.append({'offset': hex(addr), 'u16_be': hex(value),
                               'line': no, 'file_offset': hex(file_offset), 'command': token})
                for i, byte in enumerate(value.to_bytes(2, 'big')):
                    sparse[addr + i] = byte
                    origins[addr + i] = {'line': no, 'file_offset': hex(file_offset), 'command': token}
        elif token and not token.startswith('#'):
            raise ValueError(f'Unparsed initialization command at {no}: {token!r}')
        file_offset += len(line)

    def param(a, n):
        return bytes(sparse[i] for i in range(a, a + n))

    def parameter_record(a, n):
        b = param(a, n)
        return {'offset': hex(a), 'hex': b.hex(' '),
                'source_commands': [dict(offset=hex(i), **origins[i]) for i in range(a, a + n, 2)]}

    # Decode the two actual jump tables, rather than assuming sequential cases.
    preset_targets = jump(0x2021EFFE, 0x2019A114, 13)
    scene_targets = jump(0x2021EF58, 0x2019955C, 30)
    groups = []
    for effect, a, branch, scene, name in [
        (8, 0xC97, 0x2019A114, 1, 'Portrait (name inferred)'),
        (9, 0xCA0, 0x2019A12C, 2, 'Sports, T+0xAC != 2 (name inferred)'),
        (10, 0xCBB, 0x2019A144, 2, 'Sports, T+0xAC == 2 (name inferred)'),
        (11, 0xCA9, 0x2019A15C, 3, 'Landscape (name inferred)'),
        (12, 0xCB2, 0x2019A174, 4, 'Nightscape (name inferred)'),
    ]:
        assert preset_targets[effect] == branch
        b = param(a, 9)
        levels = list(b[:3]) + [x & 15 for x in b[3:8]] + [x >> 4 for x in b[3:8]]
        assert all(1 <= x <= 9 for x in levels)
        groups.append(dict(effect=effect, scene_byte=scene, candidate_name=name,
                           name_confidence='inference from scene order and official manual, not resource-ID closure',
                           branch=hex(branch), **parameter_record(a, 9),
                           normalized_13=levels, setting_raw_13=[DISPLAY_TO_RAW[x - 1] for x in levels],
                           extra_byte=b[8], extra_byte_read=effect in (8, 9, 10)))

    curves, selectors = [], []
    normal_branches = jump(0x2012B2D4, 0x2010E854, 9)
    branch_to_offset = {0x2010E854: 0x2410, 0x2010E868: 0x2412, 0x2010E87C: 0x2414,
                        0x2010E890: 0x2416, 0x2010E8A4: 0x241A, 0x2010E8B8: 0x241C,
                        0x2010E8CC: 0x241E, 0x2010E8E0: 0x2420, 0x2010E8F4: 0x2418}
    for i, branch in enumerate(normal_branches, 1):
        a = branch_to_offset[branch]
        word = int.from_bytes(param(a, 2), 'big')
        selectors.append({'display': i, 'raw': DISPLAY_TO_RAW[i - 1], 'branch': hex(branch),
                          **parameter_record(a, 2), 'lut_id': (word >> 8) & 63, 'aux_nibble': word & 15})
    for row in range(1, 23):
        a, b = 0x2012F40C + (row - 1) * 62, 0x2012FF78 + (row - 1) * 33
        x = list(struct.unpack('>31H', read(a, 62)))
        y = list(read(b, 33))
        assert x == sorted(x) and y == sorted(y)
        curves.append({'id': row, 'input_vma': hex(a), 'input_file_offset': hex(offset(a)),
                       'output_vma': hex(b), 'output_file_offset': hex(offset(b)),
                       'input_internal_u16': x, 'output_u8': y,
                       'candidate_x': [0] + x + [4095],
                       'interpretation': '31 input nodes + 2 inferred endpoints; silicon interpolation unverified'})

    masks = [int.from_bytes(param(0x129C + i * 4, 4), 'big') for i in range(5)]
    mask_records = [dict(color=c, mask=hex(m), sectors=[j for j in range(24) if m & (1 << j)],
                         **parameter_record(0x129C + 4 * i, 4)) for i, (c, m) in enumerate(zip(COLORS, masks))]
    # Normal (r4=0) color-mapper tables. Values scale encoded coefficients;
    # they are NOT measured percentages of pixel chroma.
    k80, k90, k120, k110 = [list(param(a, 24)) for a in [0xF00, 0xF18, 0xF30, 0xF48]]
    avg = lambda x, y: [int((a + b) / 2) for a, b in zip(x, y)]
    k = [k80, avg(k80, k90), k90, avg(k90, [100] * 24), [100] * 24,
         avg(k110, [100] * 24), k110, avg(k110, k120), k120]
    k_targets = jump(0x2012BE2E, 0x20113DC8, 9)
    expected_k = [0x20113DC8, 0x20113DD4, 0x20113DF4, 0x20113DFC, 0x20113E60,
                  0x20113E14, 0x20113E2C, 0x20113E34, 0x20113E54]
    assert k_targets == expected_k
    # Normal hue d0 comes from program ROM; d1 comes from launch8 parameters.
    d0 = [list(struct.unpack('>24b', read(a, 24))) for a in [0x2012D362, 0x2012D302, 0x2012D28A, 0x2012D22A]]
    d1 = [list(struct.unpack('>24b', param(a, 24))) for a in [0xF60, 0xF78, 0xF90, 0xFA8]]
    assert jump(0x2012BE1C, 0x20113C54, 9) == [0x20113C54, 0x20113C68, 0x20113CB0,
           0x20113CC4, 0x20113D9C, 0x20113CF8, 0x20113D2C, 0x20113D40, 0x20113D88]
    d0levels = [d0[0], avg(d0[0], d0[1]), d0[1], avg(d0[1], [0] * 24), [0] * 24,
                avg(d0[3], [0] * 24), d0[3], avg(d0[3], d0[2]), d0[2]]
    d1levels = [d1[0], avg(d1[0], d1[1]), d1[1], avg(d1[1], [0] * 24), [0] * 24,
                avg(d1[3], [0] * 24), d1[3], avg(d1[3], d1[2]), d1[2]]

    # Every copied instruction is matched to original firmware bytes.
    ranges = {
        'preset-selection': [(0x20199538, 0x20199604), (0x2019A0E8, 0x2019A1F0)],
        'normalized-config': [(0x20199714, 0x201997AC), (0x201999C8, 0x20199A88),
                              (0x20199CD0, 0x20199E00), (0x20199F54, 0x20199FE0)],
        'contrast': [(0x2010E80C, 0x2010E968), (0x2010EB1C, 0x2010EB80),
                     (0x20118468, 0x20118788), (0x20257430, 0x2025749C)],
        'color': [(0x2010DD5C, 0x2010DDA0), (0x2011396C, 0x20113FB4),
                  (0x201159D8, 0x20115B30), (0x20257550, 0x20257690)],
        'awb': [(0x2019A600, 0x2019A618), (0x201B01F4, 0x201B02D8),
                (0x201B40F0, 0x201B416C), (0x201AFBD8, 0x201B0130)],
        'metadata': [(0x2019C1FC, 0x2019C208), (0x201741E8, 0x20174220), (0x20174300, 0x20174344)],
    }
    evidence = {key: [] for key in ranges}
    checked = 0
    for path in sorted(DIS.glob('jlaunch3-sec*.disasm.txt')):
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            m = re.fullmatch(r'([0-9a-f]+):\t([0-9a-f ]+)\t(.*)', line)
            if not m:
                continue
            va = int(m[1], 16)
            keys = [key for key, rr in ranges.items() if any(lo <= va < hi for lo, hi in rr)]
            if not keys:
                continue
            machine = bytes.fromhex(m[2])
            assert read(va, len(machine)) == machine, (hex(va), path.name, line_no)
            checked += 1
            for key in keys:
                evidence[key].append(f'{path.name}:{line_no} | file {offset(va):#x} | {line}')
    (HERE / 'evidence').mkdir(exist_ok=True)
    for key, lines in evidence.items():
        assert lines
        (HERE / 'evidence' / f'{key}.disasm.txt').write_text('\n'.join(lines) + '\n')
    save('firmware_parameters.json', {
        'schema': 'gxr-shipped-parameter-evidence-v1',
        'source_sha256': {n: hashlib.sha256((FW / n).read_bytes()).hexdigest() for n in ['jlaunch3', 'jlaunch8']},
        'script_controls': controls, 'script_word_writes': len(writes),
        'script_decoded_bytes': len(sparse), 'runtime_pointer_initial': hex(int.from_bytes(read(0x200B2CF0, 4), 'big')),
        'evidence_boundary': 'launch8 shipped defaults reconstructed as BE words, not a live parameter dump; control-domain loader and per-unit overrides untraced',
        'preset_groups': groups, 'scene_jump_targets': list(map(hex, scene_targets)),
        'preset_variant_parameter_T_AC_u16': int.from_bytes(param(0xAC, 2), 'big'),
        'ordinary_contrast_selectors': selectors, 'curves': curves, 'color_masks': mask_records,
        'normal_sector_saturation_k_percent': k, 'normal_sector_hue_d0': d0levels, 'normal_sector_hue_d1': d1levels,
        'normal_color_table_sources': [parameter_record(a, 24) for a in range(0xF00, 0xFC0, 24)],
        'awb': {'call_chain': ['0x2019A608:C+0x23 -> AWB+0x40', '0x2019A610:C+0x22 -> AWB+0x41',
                              '0x201B029C:signed AWB+0x40/+0x41 -> 0x201B40F0',
                              '0x201B4158:0x201AFBD8(gains,230,T+0x3EE,axis_at_40,axis_at_41)'],
                'T_3ee': int.from_bytes(param(0x3EE, 1), 'big'),
                'numeric_gain_formula': None, 'axis_color_names': None},
        'verified_instruction_lines': checked,
        'unknowns': ['scene numeric IDs to resource names', 'UEEF1 loader to T lifetime and live overrides',
                     'hardware color-space, sector-angle and interpolation specification',
                     'AWB software-float complete formula and direction', 'live camera response to parameters']
    })
    with (HERE / 'ordinary_contrast.csv').open('w') as f:
        w = csv.writer(f)
        w.writerow(['display', 'raw', 'parameter_offset', 'selector_be', 'lut_id', 'node', 'candidate_input', 'output_u8'])
        for s in selectors:
            curve = curves[s['lut_id'] - 1]
            for i, (x, y) in enumerate(zip(curve['candidate_x'], curve['output_u8'])):
                w.writerow([s['display'], s['raw'], s['offset'], s['hex'], s['lut_id'], i, x, y])
    print(json.dumps({'verified_instruction_lines': checked, 'presets': len(groups),
                      'shipped_ordinary_lut_ids': [s['lut_id'] for s in selectors]}))


if __name__ == '__main__':
    main()
