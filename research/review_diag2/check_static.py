"""Read ELF tables and compare diagnostic constants with the packaged DAT."""
from pathlib import Path
import json
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_common as c


def elf(path):
    data = path.read_bytes()
    header = struct.unpack_from('>16sHHIIIIIHHHHHH', data)
    assert header[0][:6] == b'\x7fELF\x01\x02'
    sections = [struct.unpack_from('>IIIIIIIIII', data, header[6] + i * header[11])
                for i in range(header[12])]
    names = sections[header[13]]
    strings = data[names[4]:names[4] + names[5]]
    def string(table, index):
        return table[index:table.index(b'\0', index)].decode('ascii')
    by_name = {string(strings, item[0]): item for item in sections}
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        table = sections[section[6]]
        text = data[table[4]:table[4] + table[5]]
        for at in range(section[4], section[4] + section[5], section[9]):
            name, value, size, info, other, index = struct.unpack_from('>IIIBBH', data, at)
            if name:
                symbols[string(text, name)] = {'value': value, 'size': size, 'section': index,
                                               'type': info & 15}
    def symbol_bytes(name):
        symbol = symbols[name]
        section = sections[symbol['section']]
        at = section[4] + symbol['value'] - section[3]
        return data[at:at + symbol['size']]
    return data, by_name, symbols, symbol_bytes


def main():
    c.start()
    versions = {}
    for version in ('v1', 'v2'):
        engine = c.ROOT / ('firmware/engine_diag_' + version + '/candidate/local/full-r13/engine.elf')
        package = c.ROOT / ('firmware/package_v36_diag' + ('1' if version == 'v1' else '2') +
                            '/local/SD_ROOT/GXRCE.DAT')
        data, sections, symbols, get = elf(engine)
        image = package.read_bytes()
        section = sections['.engine']
        code_at, code_size = struct.unpack_from('>II', image, 132)
        assert data[section[4]:section[4] + section[5]] == image[code_at:code_at + code_size]
        expected_n = 1452 if version == 'v1' else 26316
        assert symbols['n']['size'] == expected_n and sections['.bss'][5] == expected_n
        versions[version] = {'file_sha256': c.sha(package), 'elf_sha256': c.sha(engine),
            'bss_bytes': expected_n, 'code_bytes': code_size,
            'fields': get('diag_fields'), 'layout': get('diag_layout'),
            'symbols': symbols, 'elf_data': data}
    assert versions['v1']['fields'] == versions['v2']['fields']
    assert versions['v1']['layout'] == versions['v2']['layout']
    tool = c.ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    path = c.ROOT / 'firmware/engine_diag_v2/candidate/local/full-r13/engine.elf'
    result = subprocess.run([str(tool), '-d', '-j', '.engine', str(path)],
        capture_output=True, timeout=1800, check=True)
    listing = result.stdout.decode('ascii')
    (c.LOCAL / 'compiled-v2.txt').write_text(listing)
    rows = []
    for match in re.finditer(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*?)\s*$', listing, re.M):
        rows.append((int(match[1], 16), bytes.fromhex(match[2]), match[3]))
    details = []
    symbols = versions['v2']['symbols']
    for name in ('dh_pointer', 'dh_header', 'dh_find', 'capture'):
        symbol = symbols[name]
        actual = [(at, raw, asm) for at, raw, asm in rows
                  if symbol['value'] <= at < symbol['value'] + symbol['size']]
        _, _, _, get = elf(path)
        expected = get(name)
        covered = set()
        for at, raw, asm in actual:
            offset = at - symbol['value']
            assert expected[offset:offset + len(raw)] == raw
            covered.update(range(offset, offset + len(raw)))
        assert len(covered) == symbol['size']
        details.append({'name': name, 'offset': symbol['value'], 'bytes': symbol['size'],
                        'decoded_bytes': len(covered), 'instruction_rows': len(actual)})
    raw_fields = versions['v2']['fields']
    assert len(raw_fields) == 50 * 8
    fields = []
    for at in range(0, len(raw_fields), 8):
        address, width = struct.unpack_from('>IB', raw_fields, at)
        assert width in (1, 2, 4) and address % width == 0
        assert 0x20000000 <= address and address + width <= 0x20800000
        fields.append({'address': address, 'bytes': width})
    c.save('static-results.json', {'status': 'PASS', 'dat_sha256': c.DAT_SHA,
        'elf_sha256': versions['v2']['elf_sha256'], 'bss_bytes': 26316,
        'main_request_bytes': 1104 + ((21588 + 26316 + 3) & ~3) + 6144 + 256,
        'reference_main_bytes': 75124, 'fields_identical_to_v1': True,
        'layout_identical_to_v1': True, 'field_count': len(fields),
        'decoded_functions': details, 'fields': fields,
        'snapshot_bytes': 12432, 'extra_bss_bytes': 24864})
    print('STATIC RETURN 0 FIELDS', len(fields), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        c.fail('static', error)
        raise SystemExit(1)
