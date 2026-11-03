from pathlib import Path
import hashlib
import inspect
import json
import os
import random
import runpy
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g135_gpt'
LOCAL = OUT / 'local/jobs' / os.environ.get('REVIEW_JOB', 'sample300')
DAT = ROOT / 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT'
SEED = 20261030135
sys.tracebacklimit = 0
sys.path.insert(0, str(ROOT / 'research/g135_v37'))
sys.path.insert(0, str(OUT))
from elf_fields import symbol


def describe(value):
    return {'type': type(value).__name__, 'length': len(value) if hasattr(value, '__len__') else None}


def main():
    raw = DAT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
    elf = (ROOT / 'firmware/engine_v53_g135/candidate/local/full-r13/engine.elf').read_bytes()
    entry_offset, code = symbol(elf, 'eng_project_compute')
    assert raw[entry_offset:entry_offset + len(code)] == code
    reference = runpy.run_path(str(ROOT / 'research/g135_v37/r2_oracle.py'), run_name='review_reference')
    Algorithm = reference['reference_class'](LOCAL / 'oracle')
    closure = dict(zip(Algorithm.compute.__code__.co_freevars, [c.cell_contents for c in Algorithm.compute.__closure__]))
    block = closure['block']
    assert block == raw[-17384:]
    bases = {}
    for pair, identities in closure['identities'].items():
        for identity in identities:
            bases[tuple(identity)] = pair
    target = runpy.run_path(str(ROOT / 'research/g135_v37/target_check.py'), run_name='review_target')
    target['loader'].__globals__['LOCAL'] = LOCAL / 'decode'
    Backend = target['loader']()
    frozen = LOCAL / 'snapshots'
    input_records = []
    for name in ['50mm', '28mm', 'mount']:
        source = ROOT / 'research/g135_v37/local/checks/review_g126' / ('target-state-' + name)
        destination = frozen / name
        destination.mkdir(parents=True, exist_ok=True)
        state_raw = (source / 'state.json').read_bytes()
        state = json.loads(state_raw)
        records = {}
        for row in state['regions']:
            data = (source / row['file']).read_bytes()
            assert len(data) == row['bytes']
            (destination / row['file']).write_bytes(data)
            records[row['file']] = hashlib.sha256(data).hexdigest()
        (destination / 'state.json').write_bytes(state_raw)
        assert (source / 'state.json').read_bytes() == state_raw
        assert all(hashlib.sha256((source / filename).read_bytes()).hexdigest() == expected for filename, expected in records.items())
        input_records.append({'unit': name, 'state_sha256': hashlib.sha256(state_raw).hexdigest(), 'regions': records})
    (LOCAL / 'snapshot-inputs.json').write_text(json.dumps(input_records, indent=2) + '\n')
    generator = random.Random(SEED)
    results = []
    total_steps = 0
    addresses = []
    for unit, name in enumerate(['50mm', '28mm', 'mount']):
        folder = frozen / name
        state = json.loads((folder / 'state.json').read_text())
        regions = [(item['base'], bytearray((folder / item['file']).read_bytes()), item['writable']) for item in state['regions']]
        located = target['locate'](regions, raw)
        print(json.dumps({'stage': 'located', 'unit': unit, 'result': describe(located), 'items': [describe(x) for x in located] if isinstance(located, tuple) else []}), flush=True)
        backend = Backend()
        for base, data, writable in regions:
            backend.map(base, bytes(data), writable)
        address = located
        entry = address + entry_offset
        assert backend.read(entry, len(code)) == code
        addresses.append({'unit': name, 'image_address': address, 'entry': entry})
        original = backend.read(address, len(raw))
        backend.map(0x30000000, bytes(0x20000), True)
        for sample in range(100):
            slot = generator.randrange(1, 9)
            recipe = block[64 + 16 * (unit * 8 + slot - 1):][:16]
            first = struct.unpack_from('>H', recipe, 4)[0]
            values = [100] + [0] * 9
            for index in range(first, first + recipe[2]):
                item = block[448 + 16 * index:][:16]
                point = generator.randrange(item[1])
                point_offset = struct.unpack_from('>I', item, 12)[0]
                values[item[0]] = struct.unpack_from('>h', block, point_offset + 4 * point)[0]
            algorithm = Algorithm()
            algorithm.unit = name
            algorithm.slot = slot
            stock, base = bases[(unit, slot)]
            expected = algorithm.compute(base, stock, values)
            if isinstance(expected, dict):
                print(json.dumps({'stage': 'reference-shape', 'keys': list(expected)}), flush=True)
                expected = expected.get('entry', expected.get('rows'))
            if isinstance(expected, tuple):
                print(json.dumps({'stage': 'reference-shape', 'items': [describe(x) for x in expected]}), flush=True)
                expected = expected[0]
            expected = bytes(expected)
            assert len(expected) == 552
            vector = struct.pack('>10h', *values)
            backend.write(0x300000ff, b'\x5a' + vector + b'\x5a')
            backend.write(0x30000fff, b'\x5a' + b'\xa5' * 552 + b'\x5a')
            for register in range(8, 14):
                backend.set_reg('r' + str(register), 0x12340000 + register)
            backend.set_reg('r15', 0x30010000)
            stopped = backend.call(entry, [slot, 0x30000100, 0x30001000], lr_sentinel=0x3fff0000, max_steps=3000000)
            observed = bytes(backend.read(0x30001000, 552))
            status = backend.get_reg('r0')
            assert status == 0, (unit, slot, sample, status)
            assert observed == expected, (unit, slot, sample, 'different output')
            assert backend.read(0x30000100, 20) == vector
            assert backend.read(0x300000ff, 1) == b'\x5a' and backend.read(0x30000114, 1) == b'\x5a'
            assert backend.read(0x30000fff, 1) == b'\x5a' and backend.read(0x30001228, 1) == b'\x5a'
            assert backend.get_reg('r15') == 0x30010000
            assert all(backend.get_reg('r' + str(reg)) == 0x12340000 + reg for reg in range(8, 14))
            assert backend.read(address, len(raw)) == original
            steps = getattr(stopped, 'steps', 0)
            assert steps > 0
            total_steps += steps
            row = {'unit': name, 'slot': slot, 'sample': sample, 'values': values, 'bytes_compared': 552, 'expected_sha256': hashlib.sha256(expected).hexdigest(), 'observed_sha256': hashlib.sha256(observed).hexdigest(), 'status': status, 'steps': steps}
            results.append(row)
            with (LOCAL / 'comparison.bin').open('ab') as stream:
                stream.write(struct.pack('>II10h', unit, slot, *values) + expected + observed)
            with (OUT / 'evidence/sample300-cases.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
            if (sample + 1) % 10 == 0:
                print(json.dumps({'unit': name, 'finished': sample + 1}), flush=True)
    summary = {'status': 'PASS', 'seed': SEED, 'cases': len(results), 'bytes_per_case': 552, 'total_bytes_compared': 552 * len(results), 'instruction_steps': total_steps, 'dat_sha256': hashlib.sha256(raw).hexdigest(), 'elf_sha256': hashlib.sha256(elf).hexdigest(), 'target_code_sha256': hashlib.sha256(code).hexdigest(), 'backend': 'PythonBackend M32R', 'sampled_units': 3, 'sampled_recipes': len({(x['unit'], x['slot']) for x in results}), 'addresses': addresses, 'reference_path': 'research/g135_v37/r2_oracle.py'}
    (OUT / 'evidence/sample300.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


try:
    main()
except BaseException as error:
    print(type(error).__name__, str(error)[:500], flush=True)
    trace = error.__traceback__
    while trace:
        print(Path(trace.tb_frame.f_code.co_filename).name, trace.tb_lineno, trace.tb_frame.f_code.co_name, flush=True)
        trace = trace.tb_next
    raise SystemExit(1)
