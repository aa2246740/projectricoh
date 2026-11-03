from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import stat
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
MANIFEST = ROOT / 'tools/speedlab/host_regression_r3/SHA256SUMS'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=['before', 'after'])
    args = parser.parse_args()
    start = time.monotonic()
    rows = []
    seen = set()
    for line in MANIFEST.read_text().splitlines():
        expected, relative = line.split('  ', 1)
        rel = Path(relative)
        if len(expected) != 64 or rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Invalid manifest entry')
        if relative in seen:
            raise ValueError('Repeated manifest entry: ' + relative)
        seen.add(relative)
        path = ROOT
        for part in rel.parts:
            path = path / part
            if stat.S_ISLNK(path.lstat().st_mode):
                raise ValueError('Manifest path contains a symbolic link: ' + relative)
        observed = sha(path)
        rows.append({'path': relative, 'expected': expected, 'actual': observed,
                     'bytes': path.stat().st_size, 'same': observed == expected})
    result = {
        'phase': args.phase,
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'manifest_sha256': sha(MANIFEST),
        'count': len(rows),
        'passed': sum(row['same'] for row in rows),
        'bytes': sum(row['bytes'] for row in rows),
        'wall_seconds': time.monotonic() - start,
        'nice': os.getpriority(os.PRIO_PROCESS, 0),
        'rows': rows,
    }
    target = OUT / 'evidence' / ('manifest-' + args.phase + '.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'rows'}))
    return 0 if result['count'] == result['passed'] == 13724 else 1


if __name__ == '__main__':
    raise SystemExit(main())
