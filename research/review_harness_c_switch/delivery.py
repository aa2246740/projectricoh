from pathlib import Path
import argparse
import hashlib
import json
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT = ROOT / 'research/review_harness_c_switch'
MANIFEST = OUT / 'SHA256SUMS'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def files():
    result = []
    for path in sorted(OUT.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symbolic link in review output')
        if path.is_file() and path != MANIFEST:
            result.append(path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'verify'])
    args = parser.parse_args()
    started = time.monotonic()
    if args.action == 'build':
        rows = [sha(path) + '  ' + str(path.relative_to(ROOT)) for path in files()]
        MANIFEST.write_text('\n'.join(rows) + '\n')
    paths, failures = set(), []
    for line in MANIFEST.read_text().splitlines():
        expected, relative = line.split('  ', 1)
        path = ROOT / relative
        if '..' in Path(relative).parts or Path(relative).is_absolute() or not path.is_relative_to(OUT):
            raise ValueError('Manifest path outside review output')
        if relative in paths:
            raise ValueError('Repeated manifest path')
        paths.add(relative)
        if not path.is_file() or path.is_symlink() or sha(path) != expected:
            failures.append(relative)
    actual = {str(path.relative_to(ROOT)) for path in files()}
    result = {'passed': not failures and actual == paths, 'files': len(paths),
              'failures': failures, 'extra': sorted(actual - paths), 'missing': sorted(paths - actual),
              'manifest_sha256': sha(MANIFEST), 'wall_seconds': time.monotonic() - started}
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
