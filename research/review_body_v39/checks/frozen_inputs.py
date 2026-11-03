#!/usr/bin/python3 -I
"""Record and compare the reviewed files without changing the inputs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_body_v39/evidence'
TREES = (
    'research/body_v39', 'research/body_next_steps',
    'research/review_body_reclaim_r2', 'firmware/resident_v39',
    'firmware/image_v39', 'firmware/package_v39_body_only',
    'firmware/package_v39_g149', 'firmware/engine_v39_ux',
    'firmware/engine_v58_g149', 'firmware/resident_v38',
    'tools/gxr_emulator_batch',
)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def snapshot():
    entries = {}
    for name in TREES:
        for base, dirs, files in os.walk(ROOT / name, followlinks=False):
            for part in dirs[:] + files:
                path = Path(base) / part
                key = str(path.relative_to(ROOT))
                if path.is_symlink():
                    entries[key] = {'link': os.readlink(path)}
                elif path.is_file():
                    entries[key] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    for name in ('artifacts/downloads/gxr-151.zip',):
        path = ROOT / name
        entries[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return dict(sorted(entries.items()))


def manifest_check():
    rows = []
    for line in (ROOT / 'research/body_v39/SHA256SUMS').read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT)
        actual = digest(path)
        rows.append({'path': name, 'sha256': actual, 'ok': expected == actual})
    assert len(rows) == 72 and all(row['ok'] for row in rows)
    return rows


def main():
    start = time.monotonic()
    rows = manifest_check()
    current = snapshot()
    mode = sys.argv[1]
    if mode == 'before':
        assert not (OUT / 'frozen-before.json').exists()
        result = {'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'manifest': rows, 'entries': current}
    elif mode == 'after':
        before = json.loads((OUT / 'frozen-before.json').read_text())['entries']
        different = [name for name in before.keys() | current.keys()
                     if before.get(name) != current.get(name)]
        result = {'manifest_count': len(rows), 'entry_count': len(current),
                  'different': sorted(different), 'ok': not different}
    else:
        raise SystemExit('expected before or after')
    result['elapsed_seconds'] = time.monotonic() - start
    (OUT / ('frozen-' + mode + '.json')).write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ('manifest', 'entries')}))
    print('recorded_entries', len(current))
    if result.get('ok') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
