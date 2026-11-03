from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'


def inventory():
    files = {}
    for directory in ['tools/native_harness', 'tools/gxr_emulator_batch']:
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_symlink():
                files[str(path.relative_to(ROOT))] = 'link-sha256:' + hashlib.sha256(os.readlink(path).encode()).hexdigest()
            elif path.is_file():
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1048576), b''):
                        digest.update(chunk)
                files[str(path.relative_to(ROOT))] = digest.hexdigest()
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['before', 'after'])
    args = parser.parse_args()
    started = time.monotonic()
    files = inventory()
    record = {'phase': args.phase, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'files': files, 'count': len(files), 'wall_seconds': time.monotonic() - started}
    if args.phase == 'after':
        before = json.loads((OUT / 'evidence/tools-before.json').read_text())['files']
        record['unchanged'] = files == before
        record['added'] = sorted(files.keys() - before.keys())
        record['removed'] = sorted(before.keys() - files.keys())
        record['changed'] = [key for key in files.keys() & before.keys() if files[key] != before[key]]
    (OUT / 'evidence' / ('tools-' + args.phase + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: value for key, value in record.items() if key != 'files'}))


if __name__ == '__main__':
    main()
