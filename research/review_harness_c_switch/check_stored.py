from pathlib import Path
import collections
import hashlib
import json
import re
import struct
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
SOURCE = ROOT / 'tools/speedlab/host_regression_r3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Repeated JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    def invalid(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def compare(a, b, at=''):
    if type(a) is not type(b):
        return 0, [{'path': at, 'kind': 'type'}]
    if isinstance(a, dict):
        count, differences = 0, []
        if a.keys() != b.keys():
            differences.append({'path': at, 'kind': 'keys'})
        for key in a.keys() & b.keys():
            n, diff = compare(a[key], b[key], at + '/' + str(key))
            count += n
            differences.extend(diff)
        return count, differences
    if isinstance(a, list):
        count, differences = 0, []
        if len(a) != len(b):
            differences.append({'path': at, 'kind': 'length'})
        for index, (x, y) in enumerate(zip(a, b)):
            n, diff = compare(x, y, at + '/' + str(index))
            count += n
            differences.extend(diff)
        return count, differences
    return 1, ([] if a == b else [{'path': at, 'kind': 'value', 'python': a, 'c': b}])


def normalized(value):
    if isinstance(value, str):
        return re.sub(r'(/r2-reference/)(reference|identity)-[0-9]+(\.(?:dylib|json))', r'\1\2-<process>\3', value)
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, dict):
        return {key: normalized(v) for key, v in value.items()}
    return value


def group(job):
    folders = {side: SOURCE / 'local/measurements' / side / job for side in ('python', 'c')}
    metric = {side: read(folder / 'measurement.json') for side, folder in folders.items()}
    products = {side: folder / 'products' for side, folder in folders.items()}
    files = {side: {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file()}
             for side, folder in products.items()}
    differences, metadata = [], []
    json_files, scalars, raw_equal = 0, 0, 0
    if files['python'].keys() != files['c'].keys():
        a = {name for name in files['python'] if '/r2-reference/' not in name}
        b = {name for name in files['c'] if '/r2-reference/' not in name}
        if a != b:
            differences.append({'kind': 'artifact names', 'python_only': sorted(a - b), 'c_only': sorted(b - a)})
    for name in sorted(files['python'].keys() & files['c'].keys()):
        if '/r2-reference/' in name:
            continue
        left, right = products['python'] / name, products['c'] / name
        same = files['python'][name] == files['c'][name]
        raw_equal += same
        if name.endswith('.json'):
            a, b = read(left), read(right)
            if left.name.startswith('binding-'):
                da, db = a.pop('dependencies'), b.pop('dependencies')
                common = da.keys() & db.keys()
                valid = (all(da[k] == db[k] for k in common) and
                         all(k.startswith('tools/native_harness/') for k in da.keys() - db.keys()) and
                         all(k.startswith('tools/speedlab/harness_release/') for k in db.keys() - da.keys()) and
                         all(sha(ROOT / key) == value for deps in (da, db) for key, value in deps.items()))
                metadata.append({'file': name, 'dependency_identity_checked': valid,
                                 'python_dependencies': da, 'c_dependencies': db})
                if not valid:
                    differences.append({'file': name, 'kind': 'dependency identity'})
            if left.name.startswith('result-'):
                metadata.append({'file': name, 'excluded_wrapper_seconds': [a.pop('seconds'), b.pop('seconds')]})
            count, diff = compare(a, b)
            json_files += 1
            scalars += count
            if diff:
                differences.append({'file': name, 'differences': diff})
        elif name.endswith('.jsonl'):
            a = [json.loads(line) for line in left.read_text().splitlines()]
            b = [json.loads(line) for line in right.read_text().splitlines()]
            _, diff = compare(normalized(a), normalized(b))
            if diff:
                differences.append({'file': name, 'differences': diff})
        elif not same:
            differences.append({'file': name, 'kind': 'bytes'})
    references = {}
    for side in ('python', 'c'):
        identities, libraries = [], []
        for name in files[side]:
            if '/r2-reference/' not in name:
                continue
            if re.search(r'/identity-[0-9]+\.json$', name):
                identities.append(files[side][name])
            elif re.search(r'/reference-[0-9]+\.dylib$', name):
                libraries.append({'file': name, 'sha256': files[side][name]})
            else:
                differences.append({'file': name, 'side': side, 'kind': 'unknown reference file'})
        references[side] = {'identities': sorted(identities), 'libraries': libraries}
    if (references['python']['identities'] != references['c']['identities'] or
            len(references['python']['libraries']) != len(references['c']['libraries'])):
        differences.append({'kind': 'reference source or count'})
    packets = {side: sum(p['packets'] for p in metric[side]['processes']) for side in metric}
    native = sum(p.get('native_stats', {}).get('instructions', 0) for p in metric['c']['processes'])
    for side in metric:
        m = metric[side]
        if m['result']['returncode'] != 0 or m['result']['execution'] != 'FINISHED':
            differences.append({'side': side, 'kind': 'execution'})
        if m['all_artifacts'] != files[side] or m['packets'] != packets[side]:
            differences.append({'side': side, 'kind': 'saved identity or packet receipt'})
    if packets['python'] != packets['c'] or (job != 'user-tool' and (not packets['python'] or not native)):
        differences.append({'kind': 'executed work'})
    return {'job': job, 'equal': not differences, 'differences': differences,
            'json_files': json_files, 'compared_values': scalars, 'raw_equal_files': raw_equal,
            'packets': packets, 'native_instructions': native,
            'cpu_seconds': {side: metric[side]['cpu_seconds'] for side in metric},
            'wall_seconds': {side: metric[side]['wall_seconds'] for side in metric},
            'processes': {side: len(metric[side]['processes']) for side in metric},
            'all_artifacts': files, 'reference_files': references, 'metadata_checks': metadata}


def tape_count(path):
    data = path.read_bytes()
    offset, count = 0, 0
    while offset < len(data):
        address, width, pc, origin_size, data_size = struct.unpack_from('>5I', data, offset)
        if width != data_size or not width or origin_size > 4096:
            raise ValueError('Invalid tape record')
        offset += 20 + origin_size + data_size
        if offset > len(data):
            raise ValueError('Truncated tape')
        count += 1
    return count


def tapes():
    folders = {side: SOURCE / 'run/local/tapes' / side for side in ('0', '1', 'mutant')}
    proof = {}
    for kind in ('write', 'audit'):
        names = [{p.name for p in (folders[side] / (kind + '-tapes')).glob('*.bin')} for side in ('0', '1')]
        if names[0] != names[1]:
            raise AssertionError('Tape file set differs')
        rows = []
        for name in sorted(names[0]):
            a, b = [folders[side] / (kind + '-tapes') / name for side in ('0', '1')]
            equal = a.read_bytes() == b.read_bytes()
            rows.append({'name': name, 'equal': equal, 'records': tape_count(a),
                         'bytes': a.stat().st_size, 'sha256': [sha(a), sha(b)]})
        proof[kind] = {'equal': all(row['equal'] for row in rows), 'files': len(rows),
                       'records': sum(row['records'] for row in rows),
                       'bytes': sum(row['bytes'] for row in rows), 'rows': rows}
    normal = {p.name: p.read_bytes() for p in (folders['1'] / 'audit-tapes').glob('*.bin')}
    changed = {p.name: p.read_bytes() for p in (folders['mutant'] / 'audit-tapes').glob('*.bin')}
    proof['mutation'] = {'detected': normal != changed, 'normal_records': proof['audit']['records'],
                         'changed_records': sum(tape_count(p) for p in (folders['mutant'] / 'audit-tapes').glob('*.bin'))}
    proof['scope'] = 'Existing complete C filter-off and filter-on recordings, independently read and compared; no new tape execution'
    return proof


def main():
    started = time.monotonic()
    target = OUT / 'stored'
    target.mkdir(exist_ok=False)
    jobs = [j['name'] for j in read(SOURCE / 'queue.json')['jobs']]
    results = []
    for name in jobs:
        row = group(name)
        (target / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        results.append(row)
        print(json.dumps({key: row[key] for key in ('job', 'equal', 'json_files', 'compared_values', 'differences')}), flush=True)
    regressions = [row for row in results if row['job'] != 'user-tool']
    wall = {side: sum(row['wall_seconds'][side] for row in regressions) for side in ('python', 'c')}
    cpu = {side: sum(row['cpu_seconds'][side] for row in regressions) for side in ('python', 'c')}
    tape_proof = tapes()
    (target / 'tapes.json').write_text(json.dumps(tape_proof, indent=2) + '\n')
    summary = {'passed': all(row['equal'] for row in results), 'groups': len(regressions),
               'json_files': sum(row['json_files'] for row in results),
               'compared_values': sum(row['compared_values'] for row in results),
               'packets_per_side': sum(row['packets']['python'] for row in regressions),
               'wall_seconds': wall, 'cpu_seconds': cpu,
               'wall_ratio': wall['python'] / wall['c'], 'cpu_ratio': cpu['python'] / cpu['c'],
               'verification_wall_seconds': time.monotonic() - started,
               'tapes': {kind: {k: v for k, v in value.items() if k != 'rows'}
                         if isinstance(value, dict) else value for kind, value in tape_proof.items()}}
    (target / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
