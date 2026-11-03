#!/usr/bin/python3
"""Bind the source delta (vs gen 131 and vs engine_v52_redisplay) and the compiled code to the final DAT."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g135_v37'
OLD = ROOT / 'firmware/engine_v51_g131'
NEW = ROOT / 'firmware/engine_v53_g135'
G127 = ROOT / 'firmware/engine_v48_own'
V52 = ROOT / 'firmware/engine_v52_redisplay'
OLD_FULL = OLD / 'candidate/local/full-r13'
FULL = NEW / 'candidate/local/full-r13'
DAT = ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'

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

def changed_lines(before, after):
    removed, added = [], []
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm='', n=0):
        if line.startswith('-') and not line.startswith('---'):
            removed.append(line[1:])
        elif line.startswith('+') and not line.startswith('+++'):
            added.append(line[1:])
    return removed, added

def elf_sections(elf):
    section_start = struct.unpack_from('>I', elf, 32)[0]
    section_size, count, name_index = struct.unpack_from('>HHH', elf, 46)
    sections = [struct.unpack_from('>10I', elf, section_start + index * section_size) for index in range(count)]
    names = elf[sections[name_index][4]:sections[name_index][4] + sections[name_index][5]]
    label = lambda data, index: data[index:data.index(0, index)].decode()
    return sections, names, label

def compiled(elf_path):
    """name -> (address, instruction texts without addresses/hex literals), in file order."""
    text = subprocess.check_output([str(OBJDUMP), '-d', '-j', '.engine', str(elf_path)], text=True)
    result, order, current = {}, [], None
    for line in text.splitlines():
        header = re.match(r'^([0-9a-f]+) <(.+)>:$', line)
        if header:
            if not header.group(2).startswith('.L'):
                current = header.group(2)
                result[current] = dict(address=int(header.group(1), 16), lines=[], raw=[], numbers=[])
                order.append(current)
            continue
        row = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2,8}\s+)+\s*(.*)$', line)
        if row and current:
            normal = re.sub(r'<\.L\d+(\+0x[0-9a-f]+)?>', '<L>', row.group(2))
            numbers = [int(x, 16) for x in re.findall(r'\b([0-9a-f]{3,8})\b(?= <)', normal)] + [int(x) for x in re.findall(r'#(-?\d+)', normal)]
            normal = re.sub(r'<[^>]*>', '<>', normal)
            normal = re.sub(r'#-?\d+|0x[0-9a-f]+|\b[0-9a-f]{3,8}\b(?= <)', '#', normal)
            result[current]['lines'].append(normal)
            result[current]['numbers'].extend(numbers)
            result[current]['raw'].append(row.group(2))
    return result, order

def main():
    changes, patch, old_functions, new_functions, changed_files = [], [], {}, {}, []
    for path in sorted(NEW.rglob('*')):
        relative = path.relative_to(NEW)
        if not path.is_file() or 'local' in relative.parts or path.suffix not in ('.c', '.h', '.S', '.ld'):
            continue
        previous = OLD / relative
        assert previous.is_file(), str(relative)
        old, new = previous.read_text(), path.read_text()
        if old != new:
            changed_files.append(str(relative))
            patch.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(previous.relative_to(ROOT)), tofile=str(path.relative_to(ROOT)), n=3))
        if path.suffix == '.c':
            before, after = functions(old), functions(new)
            old_functions.update({(str(relative), name): body[0] for name, body in before.items()})
            new_functions.update({(str(relative), name): body[0] for name, body in after.items()})
            for name, (body, line) in after.items():
                if name not in before or before[name][0] != body:
                    changes.append(dict(file=str(relative), function=name, line=line, source_sha256=hashlib.sha256(body.encode()).hexdigest()))
    assert set(changed_files) == {'candidate/engine_services/services.c', 'candidate/engine_services/native_seed.c',
        'candidate/containers/product/src/firmware/card_container_v2/gate.c',
        'candidate/containers/product/src/firmware/engine/core/eng_data.c', 'candidate/containers/product/ui_v2_data.c'}, changed_files
    no_other_tree_files = {str(p.relative_to(OLD)) for p in OLD.rglob('*') if p.is_file() and 'local' not in p.relative_to(OLD).parts} \
        ^ {str(p.relative_to(NEW)) for p in NEW.rglob('*') if p.is_file() and 'local' not in p.relative_to(NEW).parts}
    assert no_other_tree_files == {'candidate/build131.py', 'candidate/build135.py'}, no_other_tree_files
    expected = {'ui_view', 'rv_view_owned', 'gxr2_tweak_layout', 'eng_data_accept', 'uv_validate'}
    assert {row['function'] for row in changes} == expected, {row['function'] for row in changes}
    # the part-judgement hunks are the ones engine_v52_redisplay applied to its gen 127 base
    same_as_v52 = {}
    for name in ('services.c', 'native_seed.c'):
        relative = Path('candidate/engine_services') / name
        mine = changed_lines((OLD / relative).read_text(), (NEW / relative).read_text())
        theirs = changed_lines((G127 / relative).read_text(), (V52 / relative).read_text())
        assert mine == theirs, (name, mine, theirs)
        same_as_v52[name] = dict(removed=len(mine[0]), added=len(mine[1]))
    unchanged = {name: all(body == new_functions.get(key) for key, body in old_functions.items() if key[1] == name)
                 for name in ('settings', 'storage', 'make_plan', 'settings_match', 'eng_check_settings', 'apply_impl',
                              'write_word', 'recover_confirmed', 'ig_init', 'ig_stop', 'list_bind_impl', 'rv_settings_owned',
                              'rv_settings_entry', 'ingress', 'ig_menu', 'ig_apply', 'ig_event', 'ig_panel_open')}
    assert all(unchanged.values()), unchanged
    build_changes = []
    for before, after in ((OLD / 'candidate/common.py', NEW / 'candidate/common.py'),
                          (OLD / 'candidate/build131.py', NEW / 'candidate/build135.py'),
                          (OLD / 'candidate/containers/product/pack.py', NEW / 'candidate/containers/product/pack.py')):
        old, new = before.read_text(), after.read_text()
        patch.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile=str(before.relative_to(ROOT)), tofile=str(after.relative_to(ROOT)), n=3))
        build_changes.append(str(after.relative_to(NEW)))
    (WORK / 'source-change-vs-g131.patch').write_text(''.join(patch))
    elf = (FULL / 'engine.elf').read_bytes()
    assert elf[:6] == b'\x7fELF\x01\x02'
    sections, names, label = elf_sections(elf)
    engine = next(s for s in sections if label(names, s[0]) == '.engine')
    binary = (FULL / 'engine.bin').read_bytes()
    assert elf[engine[4]:engine[4] + engine[5]] == binary
    raw = DAT.read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 135 and raw.count(binary) == 1
    new_code, new_order = compiled(FULL / 'engine.elf')
    old_code, old_order = compiled(OLD_FULL / 'engine.elf')
    assert new_order == old_order and len(new_order) == 203
    identical = [n for n in new_order if new_code[n]['lines'] == old_code[n]['lines']]
    different = [n for n in new_order if n not in identical]
    assert different == ['rv_view_owned', 'rv_call', 'rv_api'], different
    different.remove('rv_api')
    # rv_api is the service pointer table at the end of the section: only code pointers move
    def table(path, name, code):
        data = path.read_bytes()
        sections_, names_, label_ = elf_sections(data)
        section = next(s for s in sections_ if label_(names_, s[0]) == '.engine')
        start = code[name]['address'] - section[3]
        body = data[section[4] + start:section[4] + section[5]]
        return struct.unpack('>%dI' % (len(body) // 4), body[:len(body) // 4 * 4])
    old_table, new_table = table(OLD_FULL / 'engine.elf', 'rv_api', old_code), table(FULL / 'engine.elf', 'rv_api', new_code)
    assert len(old_table) == len(new_table)
    api_shifts = sorted({y - x for x, y in zip(old_table, new_table)})
    assert api_shifts and set(api_shifts) <= {0, 8, 16}, api_shifts
    shifts = {}
    for n in identical:
        for x, y in zip(old_code[n]['numbers'], new_code[n]['numbers']):
            shifts[y - x] = shifts.get(y - x, 0) + 1
    assert all(abs(s) <= 16 and s % 4 == 0 for s in shifts), shifts  # code growth is +8 in rv_view_owned and +8 in rv_call
    delta = {n: dict(instructions_g131=len(old_code[n]['lines']), instructions_g135=len(new_code[n]['lines']),
                     added_text=[l for l in difflib.unified_diff(old_code[n]['lines'], new_code[n]['lines'], lineterm='', n=0) if l.startswith('+') and not l.startswith('+++')])
             for n in different}
    assert all(row['instructions_g135'] == row['instructions_g131'] + 2 for row in delta.values())
    (WORK / 'local').mkdir(exist_ok=True)
    (WORK / 'local/final-engine-disassembly.txt').write_text(subprocess.check_output([str(OBJDUMP), '-d', '-j', '.engine', str(FULL / 'engine.elf')], text=True))
    carriers = {'ui_view': ['rv_call'], 'rv_view_owned': ['rv_view_owned'], 'gxr2_tweak_layout': ['ig_init'],
                'eng_data_accept': ['ig_init'], 'uv_validate': ['ig_init']}
    categories = dict(address_length='无新增地址、长度、偏移或字段；只在原条件旁多读一次同一个 part 字节；请求布局、S 地址、16 字段上限不变。',
        file_operations='storage 与文件调用函数逐字相同；改动函数没有文件调用。',
        native_UI='part 1 只在名表、活动字 8、原生状态 56、tag 33、state 0x2022F71C 或 ui_block 全部成立时被接受；part 0 与 4 仍拒绝；tag 33 仍要求 overlay=32。',
        loops_memory='没有新增循环、分配、释放或栈帧；其余 201 个函数的指令序列（去掉地址和偏移数值）与 gen 131 逐条相同，数值差都是 4 的倍数且不超过 16（rv_view_owned 与 rv_call 各增长 8 字节）。')
    reviews = []
    for row in changes:
        names_ = carriers[row['function']]
        spans = {n: dict(address=new_code[n]['address'], instructions=len(new_code[n]['lines']),
                         sha256=hashlib.sha256('\n'.join(new_code[n]['raw']).encode()).hexdigest()) for n in names_ if n in new_code}
        assert spans, row
        reviews.append({**row, 'compiled': spans, **categories})
    frames = {}
    for path in (NEW / 'candidate/local/product-r13/m32r-lto-oz').glob('*.su'):
        for line in path.read_text().splitlines():
            cells = line.split('\t')
            if len(cells) >= 3 and cells[1].isdigit():
                frames[cells[0].rsplit(':', 1)[-1]] = dict(bytes=int(cells[1]), kind=cells[2])
    assert frames and all(row['kind'] == 'static' for row in frames.values())
    result = dict(status='PASS_STATIC', dat_sha256=sha(DAT), elf_sha256=sha(FULL / 'engine.elf'), dat_engine_elf_equal=True,
        changed_files=changed_files, build_changes=build_changes, changed_functions=sorted(expected), part_hunks_equal_engine_v52=same_as_v52,
        reviews=reviews, unchanged_functions=unchanged, compiled_functions=len(new_order), compiled_same_skeleton_as_g131=len(identical), address_immediate_shifts=shifts, service_table_pointer_shifts=api_shifts,
        compiled_different=delta, stack=frames, maximum_static_frame=max(row['bytes'] for row in frames.values()),
        engine_bytes=len(binary), engine_bytes_g131=len((OLD_FULL / 'engine.bin').read_bytes()), file_bytes=len(raw), camera_acceptance=False)
    (WORK / 'evidence').mkdir(exist_ok=True)
    (WORK / 'evidence/codegen-four-categories.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(name='codegen-four-categories', returncode=0, counts=dict(functions=len(reviews), files=len(changed_files), identical=len(identical)))))

if __name__ == '__main__':
    main()
