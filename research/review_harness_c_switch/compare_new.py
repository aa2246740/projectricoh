from pathlib import Path
import json
import re
import sys

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
from check_stored import ROOT, sha, read, compare, normalized


def compare_job(job):
    name = job['name']
    retry = job['group'] in ('transitions', 'values')
    run_names = {side: (('retry-' if retry else 'extra-') + side + '-' + name).replace('+', 'plus')
                 if retry else 'extra-' + side + '-' + name for side in ('python', 'c')}
    runs = {side: OUT / 'entry/local/runs' / run_names[side] for side in run_names}
    products = {side: folder / 'run/local/jobs' / name for side, folder in runs.items()}
    receipts = {side: read(folder / 'evidence/receipts' / (name + '.json')) for side, folder in runs.items()}
    files = {side: {str(p.relative_to(folder)): sha(p) for p in folder.rglob('*') if p.is_file()}
             for side, folder in products.items()}
    differences, metadata = [], []
    scalar_count, json_count = 0, 0
    ordinary = {side: {k: v for k, v in items.items() if '/r2-reference/' not in k} for side, items in files.items()}
    if ordinary['python'].keys() != ordinary['c'].keys():
        differences.append({'kind': 'product file names',
                            'python_only': sorted(ordinary['python'].keys() - ordinary['c'].keys()),
                            'c_only': sorted(ordinary['c'].keys() - ordinary['python'].keys())})

    def path_normalize(value, side):
        if isinstance(value, str):
            return value.replace(str(runs[side]), '<run>').replace(str(runs[side].relative_to(ROOT)), '<run>')
        if isinstance(value, list):
            return [path_normalize(v, side) for v in value]
        if isinstance(value, dict):
            return {k: path_normalize(v, side) for k, v in value.items()}
        return value

    for logical in sorted(ordinary['python'].keys() & ordinary['c'].keys()):
        paths = {side: products[side] / logical for side in products}
        if logical.endswith('.json'):
            a, b = read(paths['python']), read(paths['c'])
            if paths['python'].name.startswith('binding-'):
                deps = {'python': a.pop('dependencies'), 'c': b.pop('dependencies')}
                valid = all(sha(ROOT / key) == value for items in deps.values() for key, value in items.items())
                shared = deps['python'].keys() & deps['c'].keys()
                valid = valid and all(deps['python'][key] == deps['c'][key] for key in shared)
                adapter_checks = {}
                for side in deps:
                    for key in deps[side].keys() - shared:
                        path = ROOT / key
                        if path.is_relative_to(runs[side] / 'run'):
                            other = 'c' if side == 'python' else 'python'
                            relative = path.relative_to(runs[side])
                            text = path.read_text().replace(str(runs[side]), '<run>')
                            other_text = (runs[other] / relative).read_text().replace(str(runs[other]), '<run>')
                            adapter_checks[str(relative)] = text == other_text
                            valid = valid and text == other_text
                        elif not (key.startswith('tools/native_harness/') if side == 'python' else key.startswith('tools/speedlab/harness_release/')):
                            valid = False
                metadata.append({'file': logical, 'dependency_identity_checked': valid,
                                 'adapter_paths_normalized': adapter_checks, 'dependencies': deps})
                if not valid:
                    differences.append({'file': logical, 'kind': 'dependency identity'})
            if paths['python'].name.startswith('result-'):
                metadata.append({'file': logical, 'excluded_wrapper_seconds': [a.pop('seconds'), b.pop('seconds')]})
            count, diff = compare(a, b)
            scalar_count += count
            json_count += 1
            if diff:
                differences.append({'file': logical, 'differences': diff})
        elif logical.endswith('.jsonl'):
            data = {side: path_normalize(normalized([json.loads(line) for line in path.read_text().splitlines()]), side)
                    for side, path in paths.items()}
            _, diff = compare(data['python'], data['c'])
            metadata.append({'file': logical, 'run_paths_and_reference_process_names_normalized': True})
            if diff:
                differences.append({'file': logical, 'differences': diff})
        elif ordinary['python'][logical] != ordinary['c'][logical]:
            if '/decode/' in logical and logical.endswith('.txt'):
                text = {side: path.read_text().replace(str(runs[side]), '<run>') for side, path in paths.items()}
                equal = text['python'] == text['c']
                metadata.append({'file': logical, 'decode_listing_run_path_equal': equal})
                if not equal:
                    differences.append({'file': logical, 'kind': 'decoder listing'})
            else:
                differences.append({'file': logical, 'kind': 'bytes'})
    refs = {}
    for side, items in files.items():
        identities = sorted(value for key, value in items.items() if re.search(r'/r2-reference/identity-[0-9]+\.json$', key))
        libraries = {key: value for key, value in items.items() if re.search(r'/r2-reference/reference-[0-9]+\.dylib$', key)}
        refs[side] = {'identities': identities, 'libraries': libraries}
    if refs['python']['identities'] != refs['c']['identities'] or len(refs['python']['libraries']) != len(refs['c']['libraries']):
        differences.append({'kind': 'reference identities or counts'})
    metrics = {side: [read(p) for p in (folder / 'run/local/processes' / name).glob('*.json')]
               for side, folder in runs.items()}
    packets = {side: sum(row['packets'] for row in records) for side, records in metrics.items()}
    native = {key: sum(row['native_stats'].get(key, 0) for row in metrics['c'])
              for key in ['instructions', 'fallback_calls', 'fallback_steps', 'fast_writes', 'ui_guard_calls']}
    for side, receipt in receipts.items():
        if receipt['returncode'] != 0 or receipt['execution'] != 'FINISHED':
            differences.append({'side': side, 'kind': 'execution', 'receipt': receipt})
        if receipt['product_hashes'] != files[side]:
            differences.append({'side': side, 'kind': 'product hash receipt'})
    if not packets['python'] or packets['python'] != packets['c'] or native['instructions'] <= 0:
        differences.append({'kind': 'work count', 'packets': packets, 'native': native})
    return {'job': name, 'equal': not differences, 'differences': differences,
            'json_files': json_count, 'compared_values': scalar_count, 'packets': packets,
            'native_stats': native, 'processes': {side: len(rows) for side, rows in metrics.items()},
            'raw_artifacts': files, 'reference_files': refs, 'metadata_checks': metadata,
            'product_seconds': {side: receipt['seconds'] for side, receipt in receipts.items()}}


def main():
    jobs = read(OUT / 'selected-queue.json')['jobs']
    if len(sys.argv) > 1:
        jobs = [j for j in jobs if j['group'] in sys.argv[1:]]
    target = OUT / 'comparisons'
    target.mkdir(exist_ok=True)
    rows = []
    for job in jobs:
        row = compare_job(job)
        (target / (job['name'] + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        rows.append(row)
        print(json.dumps({k: row[k] for k in ['job', 'equal', 'json_files', 'compared_values', 'packets', 'differences']}), flush=True)
    summary = {'passed': all(row['equal'] for row in rows), 'groups': len(rows),
               'results': [{key: row[key] for key in ['job', 'equal', 'json_files', 'compared_values', 'packets', 'native_stats', 'product_seconds']} for row in rows]}
    (target / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
