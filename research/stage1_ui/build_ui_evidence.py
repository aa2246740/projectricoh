#!/usr/bin/env python3
"""Rebuild UI tables and address references from the unmodified firmware."""
import bisect
import json
from pathlib import Path
import re
import runpy
import struct

HERE = Path(__file__).resolve().parent
ns = runpy.run_path(str(HERE / 'analyze_ui.py'))
D, offset, DIS = ns['D'], ns['offset'], ns['DIS']
instructions = {}
for path in sorted(DIS.glob('ilaunch3-sec*.disasm.txt')):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        match = re.match(r'^([0-9a-f]+):\t([0-9a-f ]+)\t(.+)$', line)
        if match:
            va = int(match[1], 16)
            instructions[va] = (path.name, number, line, bytes.fromhex(match[2]))
addresses = sorted(instructions)


def locate(va):
    start = addresses[bisect.bisect_right(addresses, va) - 1]
    name, number, line, raw = instructions[start]
    if va == 0x2023FD38 and va >= start + len(raw):
        return {'vma': hex(va), 'file_offset': hex(offset(va)),
                'original': None, 'raw_hex': D[offset(va):offset(va)+84].hex(' '),
                'note': 'objdump omits leading zero data; consumer at 0x201FEBE8'}
    assert start <= va < start + len(raw), hex(va)
    off = offset(start)
    assert D[off:off + len(raw)] == raw
    return {'vma': hex(va), 'file_offset': hex(offset(va)),
            'original': f'{name}:{number}', 'original_line': line,
            'inside_original_word_at': va - start}


def raw(va, count):
    off = offset(va)
    return D[off:off + count]


def u32s(va, count):
    return list(struct.unpack(f'>{count}I', raw(va, count * 4)))


names = ['Vivid', 'Standard', 'Natural', 'Black & White', 'B&W (TE)', 'Setting1', 'Setting2']
ids = [0x470, 0x471, 0x575, 0x1A9, 0x307, 0x1F9, 0x1FA]
modes = [9, 1, 10, 3, 6, 4, 5]
commits = [0x202BB9C8, 0x202BB9D8, 0x202BB9E8, 0x202BB9F8,
           0x202BBA08, 0x202BBA18, 0x202BBA28]
text_index = json.loads((HERE / 'text-resource-index.json').read_text())
text_by_id = {int(item['resource_id'], 16): item for item in text_index['menu_texts']}
assert u32s(0x2022D610, 7) == [0x205BE300 + item * 4 for item in ids]
assert raw(0x2037F492, 8) == bytes([0] + modes)
assert raw(0x2022DB60 + 20, 1) == b'\x07'
assert u32s(0x2022DB60 + 12, 2) == [0x205BEAD8, 0x2022D610]
assert u32s(0x2022F5A8, 1) == [0x2022D610]
assert raw(0x2022F5AC, 1) == b'\x07'
assert u32s(0x2022F5B0, 1) == [0]
extras = [u32s(0x2023FD38 + i * 12, 3) for i in range(7)]
assert extras[:3] == [[0, 0, 0]] * 3
assert extras[3:] == [[0x205BEAD4, 0x2023FFCA, 0]] * 4
items = []
for i, (name, text_id, mode, commit) in enumerate(zip(names, ids, modes, commits), 1):
    assert text_by_id[text_id]['text'] == name
    assert f'ldi r4,#{mode} -> jl r0' in instructions[commit][2]
    items.append({'ui_index': i, 'text': name, 'resource_id': hex(text_id),
                  'pointer_table_slot': hex(0x205BE300 + text_id * 4),
                  'ilaunch4_file_offset': text_by_id[text_id]['ilaunch4_file_offset'],
                  'S_plus_36E': hex(mode), 'has_editor_subpage': i >= 4,
                  'commit': locate(commit),
                  'adj_extra_record': [hex(value) for value in extras[i - 1]]})
recall_ids = u32s(0x2023EBF0, 10)
assert recall_ids == [0x470, 0x471, 0x575, 0x1F9, 0x1FA] + [0x471] * 5
defaults = []
normalized_to_raw = [None, 7, 6, 1, 2, 3, 4, 5, 8, 9]
for name, mode, va in [('Vivid', 9, 0x201BC568),
                        ('Standard', 1, 0x201BC578),
                        ('Natural', 10, 0x201BC570)]:
    payload = raw(va, 8)
    assert payload[3:] == b'\x55' * 5
    defaults.append({'text': name, 'mode': mode, 'source': locate(va),
                     'raw_rom_hex': payload.hex(' '),
                     'normalized_contrast_sharpness_vividness': list(payload[:3]),
                     'converted_raw_globals': [normalized_to_raw[x] for x in payload[:3]],
                     'packed_color_bytes': list(payload[3:])})
tables = {'image_items': items,
          'main_descriptor': {'source': locate(0x2022DB60),
                              'raw_hex': raw(0x2022DB60, 28).hex(' ')},
          'adj_type5_descriptor': {'source': locate(0x2022F5A8),
                                   'raw_hex': raw(0x2022F5A8, 12).hex(' ')},
          'adj_index_to_raw_mode': list(raw(0x2037F492, 8)),
          'recall_text_ids': [hex(x) for x in recall_ids],
          'recall_rom_defaults': defaults,
          'evidence_kind': 'static firmware bytes and original disassembly',
          'camera_tested': False}
(HERE / 'ui-tables.json').write_text(json.dumps(tables, indent=2) + '\n')

POINTS = {
    'image_main_descriptor': 0x2022DB60, 'image_main_count': 0x2022DB74,
    'image_text_pointer_table': 0x2022D610, 'image_subpage_handler': 0x202BE220,
    'image_mode_setter': 0x20268768, 'image_mode_store': 0x20268774,
    'image_mode_getter': 0x20271FEC, 'image_main_commit': 0x202BB960,
    'image_main_postcommit': 0x202BBA2C, 'image_main_refresh': 0x202BC868,
    'adj_open': 0x202BA5C8, 'adj_function_dispatch': 0x202BA6FC,
    'adj_image_open_branch': 0x202BA764, 'adj_image_init': 0x20287080,
    'adj_image_apply': 0x202871D8, 'adj_image_limit': 0x20287264,
    'adj_image_set_mode': 0x202872C0, 'adj_descriptor': 0x2022F5A8,
    'adj_cursor_event1': 0x202C25B8, 'adj_cursor_event2': 0x202C2880,
    'adj_cursor_commit1': 0x202C27DC, 'adj_cursor_commit2': 0x202C2AA4,
    'adj_overlay_apply_call': 0x202C2ABC, 'adj_generic_commit': 0x202BB4BC,
    'adj_count': 0x2022F5AC, 'adj_raw_enum_table': 0x2037F492,
    'adj_extra_table': 0x2023FD38, 'adj_extra_type5_branch': 0x201FEBD0,
    'adj_extra_table_pointer': 0x201FEBE8, 'adj_string_dereference': 0x201FE410,
    'adj_fn2_detail_branch': 0x202BE248,
    'adj_pre_dispatch_guard': 0x202BA6F8,
    'adj_draw': 0x201FD360, 'adj_row_count': 0x201FDD10,
    'adj_background_count': 0x201FF3D4, 'adj_scroll_calculation': 0x201FE39C,
    'adj_scroll_indicators': 0x201FF288,
    'recall_entry': 0x2028A888, 'recall_count': 0x2028A8A0,
    'recall_copy': 0x2028A8F8, 'recall_source_switch': 0x2028A940,
    'recall_setting1_source': 0x2028ABE8, 'recall_setting2_source': 0x2028AC3C,
    'recall_output_conversion': 0x2028AC98, 'recall_confirm': 0x202C083C,
    'recall_confirm_copy_call': 0x202C0848, 'recall_confirm_redraw': 0x202C0860,
    'recall_draw': 0x201E3F0C, 'recall_draw_cap': 0x201E3F2C,
    'recall_label_table': 0x2023EBF0, 'recall_label_modulus': 0x201E4180,
    'recall_title_id': 0x205BF7D4,
    'editor_open': 0x2028A04C, 'editor_preserve_buffer': 0x2028A060,
    'editor_save': 0x2028A420, 'editor_save_event': 0x202BE118,
    'preset_globals_read': 0x20374560, 'preset_colors_read': 0x20374574,
    'preset_rom_read': 0x20172E70, 'preset_to_raw': 0x203748D8,
    'normalized_to_raw': 0x20167CA0, 'raw_to_editor': 0x2026FC24,
    'text_draw': 0x201D7170, 'text_ascii_detect': 0x201D2054,
    'text_ascii_convert': 0x201D73E0, 'text_ascii_menu_core': 0x201D330C,
    'text_width': 0x201D74A8,
    'preview_block_send': 0x202D6F38, 'preview_sender': 0x201709CC,
    'preview_send_call': 0x202D6FB8, 'shot_sender': 0x2017098C,
    'shot_send_call1': 0x202D6B68, 'shot_send_call2': 0x202D6CBC,
    'shot_send_call3': 0x202D6DAC, 'shot_send_call4': 0x202D6E6C,
    'shoot_block_builder': 0x202D4484, 'color_builder': 0x202D3E20,
    'color_builder_call': 0x202D47C0, 'wb_byte1': 0x202D492C,
    'wb_byte2': 0x202D493C, 'wb_getter1': 0x2026E634,
    'wb_getter2': 0x2026E69C, 'wb_enable_gate': 0x2026E704,
    'card_cache_init': 0x20361684, 'card_status_buffer': 0x2036BCA4,
    'card_six_descriptors': 0x20233748, 'card_names_attach': 0x20334C48,
    'card_popup_open': 0x20334E78, 'card_row_draw': 0x20216820,
    'card_name_convert1': 0x202169D0, 'card_row_loop_bound': 0x20216AC4,
    'card_save': 0x2011D728, 'card_my_import': 0x2011E350,
    'card_current_restore': 0x2011F580, 'card_state_enumerate': 0x20120128,
}
# RAM-only references have no ilaunch3 file offset.
ledger = {name: ({'vma': hex(va), 'file_offset': None, 'kind': 'RAM pointer slot'}
                 if name == 'recall_title_id' else locate(va))
          for name, va in POINTS.items()}
(HERE / 'ui-address-index.json').write_text(json.dumps(ledger, indent=2) + '\n')
book = ['# UI 代码与数据地址索引', '',
        '由 `python3 -I research/stage1_ui/build_ui_evidence.py` 从原固件重建。', '',
        '文件偏移均属于 `ilaunch3`。`Sxx` 指原文件 '
        '`research/tooling_m32r/disasm/ilaunch3-secxx-load-*.disasm.txt`。'
        '数据所在反汇编行只用来核对字节，不表示可执行代码。RAM 没有固件文件偏移。', '',
        '| 标识 | VMA | 文件偏移 | 原反汇编行 |',
        '| --- | --- | --- | --- |']
for name, entry in ledger.items():
    origin = entry.get('original')
    if origin:
        filename, number = origin.rsplit(':', 1)
        section = re.search(r'sec(\d+)', filename)[1]
        origin = f'S{section}:{number}'
        if entry['inside_original_word_at']:
            origin += f"，字内 +{entry['inside_original_word_at']}"
    else:
        origin = 'RAM' if entry.get('kind') else '零数据被 objdump 省略，见消费者 0x201FEBE8'
    book.append(f"| `{name}` | `{entry['vma']}` | "
                f"`{entry['file_offset']}` | {origin} |")
(HERE / 'ADDRESS_BOOK.md').write_text('\n'.join(book) + '\n')
print(json.dumps({'image_choices_checked': len(items),
                  'main_and_adj_raw_mapping_agree': True,
                  'recall_sources_checked': 5, 'rom_defaults_checked': 3,
                  'address_references_checked': len(ledger)}))
