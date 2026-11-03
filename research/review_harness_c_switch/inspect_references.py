from pathlib import Path
import collections
import hashlib
import json
import struct

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'


def inspect(path):
    data = path.read_bytes()
    if struct.unpack_from('<I', data)[0] != 0xfeedfacf:
        raise ValueError('Expected 64-bit Mach-O')
    count = struct.unpack_from('<I', data, 16)[0]
    offset = 32
    sections, install_names = {}, []
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, offset)
        if size < 8 or offset + size > len(data):
            raise ValueError('Invalid Mach-O command')
        if command == 0x19:
            section_count = struct.unpack_from('<I', data, offset + 64)[0]
            for index in range(section_count):
                row = struct.unpack_from('<16s16sQQIIIIIIII', data, offset + 72 + 80 * index)
                name = row[1].rstrip(b'\0').decode() + '/' + row[0].rstrip(b'\0').decode()
                length, start, flags = row[3], row[4], row[8]
                blob = bytes(length) if flags & 255 in (1, 12, 18) else data[start:start + length]
                if len(blob) != length:
                    raise ValueError('Truncated section')
                sections[name] = {'bytes': length, 'address': row[2], 'sha256': hashlib.sha256(blob).hexdigest()}
        if command == 0xd:
            start = struct.unpack_from('<I', data, offset + 8)[0]
            install_names.append(data[offset + start:offset + size].split(b'\0')[0].decode())
        offset += size
    return {'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest(),
            'sections': sections, 'install_names': install_names}


def main():
    rows = []
    for file in sorted((OUT / 'stored').glob('group*.json')):
        proof = json.loads(file.read_text())
        libraries = {}
        for side in ('python', 'c'):
            base = ROOT / 'tools/speedlab/host_regression_r3/local/measurements' / side / proof['job'] / 'products'
            libraries[side] = [inspect(base / row['file']) for row in proof['reference_files'][side]['libraries']]
        names = set().union(*(row['sections'].keys() for values in libraries.values() for row in values))
        section_equal = {}
        for name in sorted(names):
            counts = {side: collections.Counter(row['sections'].get(name, {}).get('sha256') for row in values)
                      for side, values in libraries.items()}
            section_equal[name] = counts['python'] == counts['c']
        row = {'job': proof['job'], 'library_counts': {side: len(values) for side, values in libraries.items()},
               'section_byte_multisets_equal': section_equal, 'libraries': libraries}
        rows.append(row)
    result = {'groups': len(rows), 'results': rows,
              'scope': 'Raw library and section hashes, addresses and install names; no whole-library byte equality claim'}
    (OUT / 'stored/reference-sections.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'groups': len(rows), 'section_results': [{k: v for k, v in row.items() if k != 'libraries'} for row in rows]}))


if __name__ == '__main__':
    main()
