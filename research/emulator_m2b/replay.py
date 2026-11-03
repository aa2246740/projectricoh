#!/usr/bin/env python3
"""Offline M2b runs, append-only evidence names, and artifact identity checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT/'tools/gxr_emulator'
OUT = HERE/'local'
PYTHON = '/usr/bin/python3'
sys.path.insert(0, str(TOOLS))
from image import Image
from manage import checksum_files, verify_sources


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def inputs(sources=False):
    initial = OUT/'initial/research-emulator-m2-inputs.json'
    if not initial.exists():
        original = ROOT/'research/emulator_m2/local/initial-inputs.json'
        shutil.copyfile(original, initial)
    rows = json.loads(initial.read_text())
    checked = []
    for row in rows:
        if not row['path'].startswith('tools/gxr_emulator/'):
            assert digest(ROOT/row['path']) == row['sha256'], row['path']
            checked.append(row['path'])
    mutable = {'m2.py', 'observe.py', 'devices.py', 'peripherals.py', 'CHANGES.md', 'SHA256SUMS'}
    for line in (OUT/'initial/gxr_emulator-SHA256SUMS').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        if relative not in mutable:
            assert digest(TOOLS/relative) == expected, relative
            checked.append('tools/gxr_emulator/'+relative)
    from unit_peer import UNIT, UNIT_SHA
    assert digest(UNIT) == UNIT_SHA
    checked.append(str(UNIT.relative_to(ROOT)))
    Image()
    return {'frozen_inputs': checked,
            'gnu_sources': verify_sources() if sources else 'not rescanned'}


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    previous = ROOT/'research/emulator_m2/local'
    for name in ('final-cold-stop.pkl', 'final-cold-stop.json',
                 'unit-ready-probe-stop.pkl', 'unit-ready-probe-stop.json',
                 'nand-reflector.pages.json', 'unit-info-synthetic.bin',
                 'unit-info-synthetic.json', 'unit-ready-events.bin'):
        destination = OUT/name
        if destination.exists():
            assert digest(destination) == digest(previous/name), name
        else:
            shutil.copyfile(previous/name, destination)
    return inputs()


def run(name, arguments):
    if Path(name).name != name or any((OUT/(name+suffix)).exists()
            for suffix in ('.json', '.stdout.txt', '.stderr.txt', '-sources')):
        raise ValueError('choose a fresh evidence name')
    inputs()
    archive = OUT/(name+'-sources')
    archive.mkdir()
    for path in TOOLS.glob('*.py'):
        shutil.copyfile(path, archive/path.name)
    shutil.copyfile(Path(__file__), archive/'research-replay.py')
    command = [PYTHON, '-I', '-B', str(TOOLS/'m2.py'), '--output-dir', str(OUT),
               '--name', name, '--checkpoints', *arguments]
    (OUT/(name+'-command.json')).write_text(json.dumps(command, indent=2)+'\n')
    with (OUT/(name+'.stdout.txt')).open('x') as stdout, \
            (OUT/(name+'.stderr.txt')).open('x') as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
    print(json.dumps({'name': name, 'exit_code': result.returncode}), flush=True)
    if result.returncode:
        print((OUT/(name+'.stderr.txt')).read_text(), file=sys.stderr)
        raise SystemExit(result.returncode)
    result = json.loads((OUT/(name+'.json')).read_text())
    print(json.dumps({key: result[key] for key in ('steps', 'stop', 'elapsed_sec')}, indent=2))
    observed = result['observations']
    print(json.dumps({key: observed[key] for key in
                      ('entry_hits', 'scheduled', 'created_queues', 'ui_initializers')}, indent=2))


def tool_files():
    rows = list(checksum_files())
    library = TOOLS/'build/libgxr_m32r.dylib'
    rows.append((library, str(library.relative_to(TOOLS))))
    return sorted(rows, key=lambda row: row[1])


def research_files():
    return [(path, str(path.relative_to(ROOT))) for path in sorted(HERE.rglob('*'))
            if path.is_file() and path != HERE/'SHA256SUMS'
            and path.relative_to(HERE).parts[0] != 'tmp'
            and '__pycache__' not in path.relative_to(HERE).parts]


def manifest_rows(manifest, base):
    rows = {}
    for line in manifest.read_text().splitlines():
        sha, relative = line.split('  ', 1)
        if relative in rows or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('invalid manifest path: '+relative)
        if digest(base/relative) != sha:
            raise ValueError('checksum mismatch: '+relative)
        rows[relative] = sha
    return rows


def checksums():
    counts = {}
    for manifest, base, files in ((TOOLS/'SHA256SUMS', TOOLS, tool_files()),
                                  (HERE/'SHA256SUMS', ROOT, research_files())):
        rows = manifest_rows(manifest, base)
        if set(rows) != {relative for _, relative in files}:
            raise ValueError('file census changed: '+str(manifest))
        counts[str(manifest.relative_to(ROOT))] = len(rows)
    return counts


def seal():
    inputs()
    previous = ROOT/'research/emulator_m2/SHA256SUMS'
    previous_count = len(manifest_rows(previous, ROOT))
    for manifest, files in ((TOOLS/'SHA256SUMS', tool_files()),
                            (HERE/'SHA256SUMS', research_files())):
        manifest.write_text(''.join(f'{digest(path)}  {relative}\n'
                                    for path, relative in files))
    return {'previous_m2_files': previous_count, 'current': checksums()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('prepare')
    check = commands.add_parser('inputs')
    check.add_argument('--sources', action='store_true')
    commands.add_parser('seal')
    commands.add_parser('checksums')
    execute = commands.add_parser('run')
    execute.add_argument('name')
    execute.add_argument('arguments', nargs=argparse.REMAINDER)
    repeat = commands.add_parser('repeat')
    repeat.add_argument('reference')
    repeat.add_argument('name')
    args = parser.parse_args()
    if args.command == 'prepare':
        print(json.dumps(prepare(), indent=2))
    elif args.command == 'inputs':
        print(json.dumps(inputs(args.sources), indent=2))
    elif args.command == 'seal':
        print(json.dumps(seal(), indent=2))
    elif args.command == 'checksums':
        print(json.dumps(checksums(), indent=2))
    elif args.command == 'repeat':
        if any(Path(value).name != value for value in (args.reference, args.name)):
            parser.error('simple evidence names required')
        if any((OUT/(args.name+suffix)).exists() for suffix in
               ('.json', '.stdout.txt', '.stderr.txt')):
            parser.error('choose a fresh evidence name')
        command = [PYTHON, '-I', '-B', str(HERE/'archived_run.py'), args.reference, args.name]
        with (OUT/(args.name+'.stdout.txt')).open('x') as stdout, \
                (OUT/(args.name+'.stderr.txt')).open('x') as stderr:
            subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=True)
        result = json.loads((OUT/(args.name+'.json')).read_text())
        print(json.dumps({'steps': result['steps'], 'stop': result['stop']}, indent=2))
    else:
        run(args.name, args.arguments)


if __name__ == '__main__':
    main()
