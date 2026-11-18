"""Extract official module data; no firmware or card writer is provided."""
import re
import struct
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import support as s

UNITS = {'50mm': 'jlaunch3', '28mm': 'qlaunch3', 'mount': 'l08firm3'}


class Image:
    def __init__(self, name):
        self.path = s.source(s.FW / name)
        self.data = self.path.read_bytes()
        self.sections = [struct.unpack_from('>IIIII', self.data, 32 + 20*i)[:3] for i in range(16)]

    def offset(self, va, n):
        hits = [f + 512 + va - v for f, v, size in self.sections if v <= va and va+n <= v+size]
        assert len(hits) == 1
        return hits[0]

    def raw(self, va, n):
        a = self.offset(va, n)
        return self.data[a:a+n]


def script_bytes(name):
    data = s.source(s.FW / name).read_bytes()
    result, origins = {}, {}
    addr = domain = None
    pos = 512
    for line in data[512:].splitlines(keepends=True):
        token = line.strip().decode('latin1')
        m = re.fullmatch(r'([XVWU])([0-9a-fA-F]{4})', token)
        if m:
            op, v = m[1], int(m[2], 16)
            if op == 'U':
                domain = v
            elif op == 'V':
                addr = v
            elif op == 'W':
                assert domain == 0xEEF1 and addr is not None
                for j, b in enumerate(v.to_bytes(2, 'big')):
                    result[addr+j] = b
                    origins[addr+j] = pos
        elif token and not token.startswith('#'):
            raise ValueError(token)
        pos += len(line)
    return result, origins


def levels(a, neutral):
    a = np.asarray(a, float)
    z = np.full(24, neutral, float)
    avg = lambda x, y: np.trunc((x+y)/2)
    return np.array([a[0], avg(a[0], a[1]), a[1], avg(a[1], z), z,
                     avg(a[3], z), a[3], avg(a[3], a[2]), a[2]])


def extract():
    tables = s.read('research/multi_module/local/tables.json')
    ids = s.read('research/multi_module/local/defaults_identity.json')
    comparison = s.read('research/multi_module/local/inputs_before.json')
    units = {}
    for unit, name in UNITS.items():
        im = Image(name)
        rows = {}
        for q in tables[name]:
            b = im.raw(q['vma'], q['size'])
            assert b.hex() == q['hex'] and s.digest(im.path) in str(comparison)
            rows[q['label']] = {'hex': b.hex(), 'file_offset': im.offset(q['vma'], q['size']),
                                'vma': q['vma'], 'sha256': q['sha256']}
        embedded = im.data[ids[name]['embedded_file']:ids[name]['embedded_file']+0x4000]
        sparse, origins = script_bytes(name[:-1]+'8')
        groups = []
        for base in (0xF00, 0xFC0, 0x1090, 0x1160):
            # The normal group is 192 bytes; the remaining groups include a 16-byte gap.
            n = 0xC0 if base == 0xF00 else 0xD0
            raw = bytes(sparse[i] for i in range(base, base+n))
            assert raw == embedded[base:base+n]
            groups.append({'t': base, 'hex': raw.hex(), 'script_file_first': origins[base]})
        masks = np.array([int.from_bytes(embedded[0x129C+4*i:0x12A0+4*i], 'big') for i in range(5)])
        assert bytes(sparse[i] for i in range(0x129C, 0x12B0)) == embedded[0x129C:0x12B0]
        # These four records are selected by the normal-context ROM getter.
        # Their locations are verified in local/rom_getter_checks.json by audit.py.
        matrix_va = next(q['vma'] for q in tables[name] if q['label'] == 'matrix1_2')
        d0_records = []
        for delta in (0x2A2, 0x242, 0x1CA, 0x16A):
            va = matrix_va + delta
            b = im.raw(va, 24)
            d0_records.append({'vma': va, 'file_offset': im.offset(va, 24), 'hex': b.hex()})
        normal = embedded[0xF00:0xFC0]
        d0 = np.array([struct.unpack('>24b', bytes.fromhex(q['hex'])) for q in d0_records])
        d1 = np.array([struct.unpack('>24b', normal[i:i+24]) for i in (96, 120, 144, 168)])
        k = np.array([list(normal[i:i+24]) for i in (0, 24, 48, 72)])
        units[unit] = {'firmware': name, 'sha256': s.digest(im.path), 'rows': rows,
                       't_groups': groups, 'mask': masks, 'rom_d0': d0_records,
                       'd0_levels': levels(d0, 0), 'd1_levels': levels(d1, 0),
                       'sat_levels': levels(k, 100), 'vividness_levels': list(embedded[0xFF0:0xFF9]),
                       't_embedded_file': ids[name]['embedded_file']}
    s.dump('local/official_parameters.json', {'schema': 'module-adapt-official/1', 'units': units})
    return units


if __name__ == '__main__':
    s.guard()
    u = extract()
    s.finish('local/extract_inputs.json')
    print('已从官方文件读取三单元原厂行、四组 T 参数、mask 和 ROM d0。')
