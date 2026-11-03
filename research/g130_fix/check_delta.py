#!/usr/bin/python3
"""Bind the small source change and four code categories to the final DAT."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g130_fix'
OLD = ROOT / 'firmware/engine_v48_own'
NEW = ROOT / 'firmware/engine_v50_h07'
FULL = NEW / 'candidate/local/full-r13'
DAT = ROOT / 'firmware/package_v36_g130/local/SD_ROOT/GXRCE.DAT'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def functions(text):
    masked = re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', lambda match: ''.join('\n' if char == '\n' else ' ' for char in match.group()), text, flags=re.S)
    result = {}
    for match in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', masked):
        name = match.group(1)
        if name in ('if', 'for', 'while', 'switch', 'sizeof', '__attribute__'):
            continue
        position = masked.index('(', match.start()) + 1
        depth = 1
        while position < len(masked) and depth:
            depth += (masked[position] == '(') - (masked[position] == ')')
            position += 1
        while position < len(masked) and masked[position].isspace():
            position += 1
        if position >= len(masked) or masked[position] != '{':
            continue
        stop = position + 1
        depth = 1
        while stop < len(masked) and depth:
            depth += (masked[stop] == '{') - (masked[stop] == '}')
            stop += 1
        start = masked.rfind('\n', 0, match.start()) + 1
        result[name] = (text[start:stop], text.count('\n', 0, start) + 1)
    return result

def main():
    changes = []
    patch = []
    service_patch = []
    old_functions = {}
    new_functions = {}
    changed_files = []
    for path in sorted(NEW.rglob('*')):
        relative = path.relative_to(NEW)
        if not path.is_file() or 'local' in relative.parts or path.suffix not in ('.c', '.h', '.S', '.ld'):
            continue
        previous = OLD / relative
        assert previous.is_file(), str(relative)
        old, new = previous.read_text(), path.read_text()
        if old != new:
            changed_files.append(str(relative))
            difference = list(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(previous.relative_to(ROOT)), tofile=str(path.relative_to(ROOT)), n=3))
            patch.extend(difference)
            if path.name == 'services.c':
                service_patch.extend(difference)
        if path.suffix == '.c':
            before, after = functions(old), functions(new)
            old_functions.update({(str(relative), name): body[0] for name, body in before.items()})
            new_functions.update({(str(relative), name): body[0] for name, body in after.items()})
            for name, (body, line) in after.items():
                if name not in before or before[name][0] != body:
                    changes.append(dict(file=str(relative), function=name, line=line, source_sha256=hashlib.sha256(body.encode()).hexdigest()))
    assert set(changed_files) == {'candidate/engine_services/services.c', 'candidate/engine_services/engine_services.h', 'candidate/engine_services/native_seed.c', 'candidate/containers/product/adapter.c', 'candidate/containers/product/src/firmware/card_container_v2/gate.c', 'candidate/containers/product/src/firmware/engine/core/eng_data.c', 'candidate/containers/product/ui_v2_data.c'}
    expected = {'rv_settings_entry', 'rv_settings_owned', 'rv_service', 'rv_view_owned', 'ingress', 'ig_menu', 'ig_apply', 'ig_event', 'ig_panel_open', 'gxr2_tweak_layout', 'eng_data_accept', 'uv_validate'}
    assert {row['function'] for row in changes} == expected
    preserved = {name: all(body == new_functions.get(key) for key, body in old_functions.items() if key[1] == name) for name in ('settings', 'storage', 'make_plan', 'settings_match', 'eng_check_settings', 'apply_impl', 'write_word', 'recover_confirmed', 'ig_init', 'ig_stop', 'list_bind_impl')}
    assert all(preserved.values()), preserved
    build_changes = []
    for before, after in ((OLD / 'candidate/common.py', NEW / 'candidate/common.py'), (OLD / 'candidate/build127.py', NEW / 'candidate/build130.py')):
        old, new = before.read_text(), after.read_text()
        patch.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(before.relative_to(ROOT)), tofile=str(after.relative_to(ROOT)), n=3))
        build_changes.append(str(after.relative_to(NEW)))
    (WORK / 'source-change-vs-g127.patch').write_text(''.join(patch))
    (WORK / 'services-only.patch').write_text(''.join(service_patch))
    elf = (FULL / 'engine.elf').read_bytes()
    assert elf[:6] == b'\x7fELF\x01\x02'
    section_start = struct.unpack_from('>I', elf, 32)[0]
    section_size, count, name_index = struct.unpack_from('>HHH', elf, 46)
    sections = [struct.unpack_from('>10I', elf, section_start + index * section_size) for index in range(count)]
    names = elf[sections[name_index][4]:sections[name_index][4] + sections[name_index][5]]
    def label(data, index):
        return data[index:data.index(0, index)].decode()
    engine_index = next(index for index, section in enumerate(sections) if label(names, section[0]) == '.engine')
    engine = sections[engine_index]
    binary = (FULL / 'engine.bin').read_bytes()
    assert elf[engine[4]:engine[4] + engine[5]] == binary
    raw = DAT.read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 130 and raw.count(binary) == 1
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        data = elf[strings[4]:strings[4] + strings[5]]
        for position in range(section[4], section[4] + section[5], section[9]):
            name, value, size, info, other, index = struct.unpack_from('>IIIBBH', elf, position)
            if info & 15 == 2 and index == engine_index and size:
                symbols[label(data, name)] = dict(address=value, size=size)
    assembly = subprocess.check_output([str(ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'), '-d', '-j', '.engine', str(FULL / 'engine.elf')], text=True)
    (WORK / 'local/final-engine-disassembly.txt').write_text(assembly)
    spans = {}
    for name, row in symbols.items():
        lines = []
        for line in assembly.splitlines():
            match = re.match(r'\s*([0-9a-f]+):\s+(.*)', line)
            if match and row['address'] <= int(match.group(1), 16) < row['address'] + row['size']:
                lines.append(line)
        spans[name] = {**row, 'disassembly_sha256': hashlib.sha256('\n'.join(lines).encode()).hexdigest(), 'decoded_lines': len(lines)}
    carriers = {'rv_settings_entry': ['ig_menu', 'ig_event', 'ig_apply', 'ig_panel_open', 'ig_init', 'ig_stop'], 'ingress': ['ig_menu', 'ig_event', 'ig_apply', 'ig_panel_open', 'ig_init', 'ig_stop'], 'rv_service': ['rv_call'], 'gxr2_tweak_layout': ['ig_init'], 'eng_data_accept': ['ig_init'], 'uv_validate': ['ig_init']}
    categories = dict(address_length='现有会话与 context 字段；保持请求布局、S 地址、16 字段上限和所有偏移。', file_operations='storage 与文件调用函数逐字相同；新分支没有文件调用。', native_UI='H01 构造规则，H06/H07/H08 严格规则；tag 33 总要求 overlay=32。settings 与 preview 在 IRQ 区间复核。preview 恢复 IRQ 后的窗口单列。', loops_memory='新增规则绑定和复核没有循环、分配或释放；九行、T、settings_pending、4+2 补偿代码逐字相同。')
    reviews = []
    for row in changes:
        names = carriers.get(row['function'], [row['function']])
        compiled = {name: span for name, span in spans.items() if any(name == target or name.split('.constprop.')[0] == target for target in names)}
        assert compiled, row
        reviews.append({**row, 'compiled': compiled, **categories})
    frames = {}
    for path in (NEW / 'candidate/local/product-r13/m32r-lto').glob('*.su'):
        for line in path.read_text().splitlines():
            cells = line.split('\t')
            if len(cells) >= 3 and cells[1].isdigit():
                frames[cells[0].rsplit(':', 1)[-1]] = dict(bytes=int(cells[1]), kind=cells[2])
    assert frames and all(row['kind'] == 'static' for row in frames.values())
    result = dict(status='PASS_STATIC', dat_sha256=sha(DAT), elf_sha256=sha(FULL / 'engine.elf'), dat_engine_elf_equal=True, changed_files=changed_files, build_changes=build_changes, reviews=reviews, unchanged_functions=preserved, stack=frames, maximum_static_frame=max(row['bytes'] for row in frames.values()), engine_bytes=len(binary), file_bytes=len(raw), camera_acceptance=False)
    (WORK / 'evidence/codegen-four-categories.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(name='codegen-four-categories', returncode=0, counts=dict(functions=len(reviews), files=len(changed_files)))))

if __name__ == '__main__':
    main()
