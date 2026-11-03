#!/usr/bin/env python3
"""Use the repository's inert-data fetcher, with an explicitly scoped destination."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    a = p.parse_args()
    repo = a.repo.resolve()
    dest = a.destination.resolve()
    assert dest == repo / 'artifacts/downloads/bastibe-gr3'
    spec = importlib.util.spec_from_file_location('inert_fetch', repo / 'research/color_references/fetch_source.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.SCRATCH = dest
    manifest = json.loads((repo / 'research/color_references/source_manifest.json').read_text())
    receipts = []
    for name in ('dng', 'standard', 'positive', 'negative'):
        key = 'bastibe_gr3_' + name
        row = next(r for r in manifest['downloads'] if r['id'] == key)
        assert row['url'] in row['re_fetch_instruction']
        filename = Path(row['local_path']).name
        path = dest / 'downloads' / key / filename
        if not path.exists():
            path = helper.fetch(key, row['url'], filename, row['terms'], quiet=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == row['sha256'], key
        receipts.append({'id': key, 'path': str(path.relative_to(repo)), 'bytes': path.stat().st_size,
                         'sha256': digest, 'matches_manifest': True})
        print(key, path.stat().st_size, digest, flush=True)
    (repo / 'research/color_fit_v2/gr_round5/local/downloads_verified.json').write_text(
        json.dumps(receipts, indent=2) + '\n')


if __name__ == '__main__':
    main()
