#!/usr/bin/env python3
"""Verify source archives and index every bounded M2b run without rewriting it."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
OUT = HERE/'local'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def arguments(row):
    return {key: value for key, value in row['arguments'].items()
            if key not in ('name', 'output_dir')}


def main():
    name, = sys.argv[1:]
    if Path(name).name != name:
        raise ValueError('simple evidence name required')
    target = OUT/(name+'.json')
    if target.exists():
        raise ValueError('choose a fresh evidence name')
    runs = {}
    for path in sorted(OUT.glob('*.json')):
        row = json.loads(path.read_text())
        if isinstance(row, dict) and all(key in row for key in
                ('arguments', 'source_hashes', 'start_step', 'steps', 'stop')):
            runs[path.stem] = row
    archives = {}
    for reference, row in runs.items():
        archive = OUT/(reference+'-sources')
        if archive.is_dir():
            for source, expected in row['source_hashes'].items():
                assert digest(archive/source) == expected, (reference, source)
            archives[reference] = row
    rows = []
    for reference, row in runs.items():
        candidates = [name for name, saved in archives.items()
                      if saved['source_hashes'] == row['source_hashes']
                      and arguments(saved) == arguments(row)]
        assert candidates, ('source archive or exact reference missing', reference)
        canonical = reference if reference in candidates else candidates[0]
        checkpoint = OUT/(reference+'-stop.pkl')
        metadata = json.loads(checkpoint.with_suffix('.json').read_text())
        assert digest(checkpoint) == metadata['sha256'], reference
        if row['start_checkpoint']:
            start = row['start_checkpoint']
            assert digest(OUT/start['file']) == start['sha256'], reference
        observed = row['observations']
        rows.append({'name': reference, 'source_reference': canonical,
                     'start_step': row['start_step'], 'end_step': row['steps'],
                     'stop': row['stop'], 'source_files': len(row['source_hashes']),
                     'result_sha256': digest(OUT/(reference+'.json')),
                     'checkpoint_sha256': metadata['sha256'],
                     'native_tasks_created': sorted(int(value) for value in
                                                    observed.get('created_tasks', {})),
                     'queues_created': sorted(int(value) for value in observed['created_queues']),
                     'task_schedules': {task: observed['scheduled'].get(str(task), 0)
                                       for task in (6, 8, 28)}})
    result = {'status': 'PASS', 'runs': rows, 'run_count': len(rows),
              'source_archives': len(archives),
              'scope': 'Checksums, source identity and checkpoint references; '
                       'a preserved fault remains a fault.',
              'runner_sha256': digest(Path(__file__))}
    with target.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'runs': len(rows),
                      'source_archives': len(archives)}))


if __name__ == '__main__':
    main()
