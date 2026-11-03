"""Compare acceptance JSON values exactly, removing only named time fields."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
TIME_FIELDS = frozenset(('elapsed', 'elapsed_s', 'elapsed_seconds', 'wall', 'wall_seconds',
                         'cpu', 'cpu_seconds', 'duration', 'duration_seconds', 'seconds'))


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in TIME_FIELDS}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def compare_values(left, right):
    differences, leaves, containers = [], 0, 0
    def walk(a, b, path):
        nonlocal leaves, containers
        if type(a) is not type(b):
            differences.append(dict(path=path, reason='type'))
        elif isinstance(a, dict):
            containers += 1
            if a.keys() != b.keys():
                differences.append(dict(path=path, reason='keys'))
            for key in a.keys() & b.keys():
                walk(a[key], b[key], path+'/'+str(key))
        elif isinstance(a, list):
            containers += 1
            if len(a) != len(b):
                differences.append(dict(path=path, reason='count'))
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path+'/'+str(i))
        else:
            leaves += 1
            if a != b:
                differences.append(dict(path=path, reason='value',
                    left_sha256=hashlib.sha256(repr(a).encode()).hexdigest(),
                    right_sha256=hashlib.sha256(repr(b).encode()).hexdigest()))
    walk(clean(left), clean(right), '')
    return dict(equal=not differences, values=leaves, containers=containers, differences=differences)


def outputs(folder):
    mapping = json.loads((folder/'output_map.json').read_text())
    results, identities, diagnostics = {}, {}, {}
    for source, destination in mapping.items():
        path = Path(destination)
        name = Path(source).name
        if path.suffix != '.json' or not path.is_file():
            continue
        try:
            value = json.loads(path.read_text())
        except ValueError:
            continue
        if name.startswith(('dependencies-', 'target-map-')):
            identities[name] = value
        elif name.startswith('session-interface-'):
            diagnostics[name] = value
        else:
            results[name] = value
    return results, identities, diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('left')
    parser.add_argument('right')
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    a, b = HERE/'local'/args.left, HERE/'local'/args.right
    sa, sb = (json.loads((p/'summary.json').read_text()) for p in (a, b))
    left, li, ld = outputs(a)
    right, ri, rd = outputs(b)
    reports = {}
    for name in sorted(left.keys() | right.keys()):
        if name not in left or name not in right:
            reports[name] = dict(equal=False, differences=[dict(reason='missing result')])
        else:
            reports[name] = compare_values(left[name], right[name])
    conformance = not reports and 'conformance' in args.name
    equal = (sa['returncode'] == sb['returncode'] and sa['returncode'] != 99 and bool(reports or conformance)
             and all(x['equal'] for x in reports.values()))
    if conformance:
        equal = equal and sa['returncode'] == 0 and sa.get('stdout_sha256') == sb.get('stdout_sha256') and sa['stdout_lines'] == sb['stdout_lines'] == 1
    diagnostics = {name: compare_values(ld[name], rd[name]) for name in ld.keys() & rd.keys()}
    report = dict(name=args.name, equal=equal, returncodes=[sa['returncode'], sb['returncode']],
                  both_acceptance_successful=sa['returncode']==sb['returncode']==0,
                  result_files=reports, conformance=conformance,
                  identity_file_counts=[len(li), len(ri)], diagnostics=diagnostics,
                  removed_time_field_names=sorted(TIME_FIELDS),
                  runs=[args.left, args.right])
    folder = HERE/'equivalence'
    folder.mkdir(exist_ok=True)
    (folder/(args.name+'.json')).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(name=args.name, equal=equal, result_count=len(reports),
                         differences=sum(len(x.get('differences', ())) for x in reports.values()))))
    return 0 if equal else 1


if __name__ == '__main__':
    raise SystemExit(main())
